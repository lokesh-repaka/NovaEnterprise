"""Retrieval execution node for LangGraph research workflow (P9-4, F6, F7, F8, Claude.md §3.1, §5, §7.3).

Primary Responsibilities:
- Execute multi-store lookups across Graph, SQL, and Hybrid/Vector stores per sub-question strategy.
- Graph retrieval via typed domain traversals exposing executed Cypher and graph locators (F8).
- SQL retrieval restricted to read-only allowlisted tables via validate_sql (F7).
- Hybrid document retrieval with BM25 + dense vector + RRF + reranking (F6).
- Resilient store failure handling: records errors without crashing workflow (Claude.md §7.3).
- Telemetry recording via tracer.node() and tracer.record_query().
- Return partial state dictionary updating: evidence, errors, and metadata.
"""

from __future__ import annotations

from typing import Any

from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from backend.app.schemas.common import Evidence
from rag.graph_retrieval import (
    execute_governed_traversal,
    execute_read_only_cypher,
)
from rag.retriever import retrieve_hybrid
from rag.sql_retrieval import execute_governed_sql

logger = get_logger("agents.nodes.execute_retrieval")

# Standard entity slug mapping for sample domain data
_ENTITY_ID_MAP = {
    "payments api": "svc-payments-api",
    "auth service": "svc-identity",
    "identity service": "svc-identity",
    "core banking": "svc-core-banking",
    "notification service": "svc-notifications",
}


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _resolve_service_id(entity: str | None) -> str:
    """Resolve an entity name into its canonical service ID slug."""
    if not entity:
        return "svc-payments-api"
    cleaned = entity.strip().lower()
    if cleaned in _ENTITY_ID_MAP:
        return _ENTITY_ID_MAP[cleaned]
    if cleaned.startswith("svc-"):
        return cleaned
    return f"svc-{cleaned.replace(' ', '-')}"


def _execute_graph_sub_question(
    sub_q_id: str,
    question: str,
    target_entity: str | None,
) -> tuple[list[Evidence], str]:
    """Execute governed graph retrieval for a sub-question (F8)."""
    service_id = _resolve_service_id(target_entity)
    q_lower = question.lower()
    executed_spec = ""

    # 1. Customer impact or incident association
    if any(k in q_lower for k in ("impact", "customer", "customers", "outage")):
        executed_spec = f"traversal:service_incidents(service_id={service_id})"
        results = execute_governed_traversal(
            "service_incidents",
            {"service_id": service_id},
            sub_question_id=sub_q_id,
        )
        if results:
            return results, executed_spec

        # Fallback to incident blast radius
        executed_spec = "traversal:incident_blast_radius(incident_id=inc-2021)"
        results = execute_governed_traversal(
            "incident_blast_radius",
            {"incident_id": "inc-2021"},
            sub_question_id=sub_q_id,
        )
        if results:
            return results, executed_spec

    # 2. Team ownership and service dependencies
    if any(
        k in q_lower for k in ("team", "own", "ownership", "depend", "dependencies")
    ):
        executed_spec = f"traversal:service_dependencies(service_id={service_id})"
        results = execute_governed_traversal(
            "service_dependencies",
            {"service_id": service_id},
            sub_question_id=sub_q_id,
        )
        if results:
            return results, executed_spec

        executed_spec = "traversal:team_ownership(team_id=team-payments)"
        results = execute_governed_traversal(
            "team_ownership",
            {"team_id": "team-payments"},
            sub_question_id=sub_q_id,
        )
        if results:
            return results, executed_spec

    # 3. Read-only Cypher query fallback
    cypher = (
        "MATCH (s:Service {id: $service_id}) "
        "OPTIONAL MATCH (s)-[r]->(target) "
        "RETURN s, r, target"
    )
    executed_spec = cypher
    results = execute_read_only_cypher(
        cypher=cypher,
        params={"service_id": service_id},
        sub_question_id=sub_q_id,
    )
    return results, executed_spec


def _execute_sql_sub_question(
    sub_q_id: str,
    question: str,
    target_entity: str | None,
    time_range: dict[str, str] | None = None,
) -> tuple[list[Evidence], str]:
    """Execute governed SQL query against allowlisted tables (F7)."""
    service_id = _resolve_service_id(target_entity)
    q_lower = question.lower()
    params: dict[str, Any] = {}

    if any(
        k in q_lower for k in ("incident", "outage", "sev", "resolution", "started")
    ):
        sql_str = (
            "SELECT id, title, severity, status, root_cause, impacted_service_id, "
            "occurred_at, resolved_at FROM incidents "
            "WHERE impacted_service_id = :service_id"
        )
        params["service_id"] = service_id
    elif any(k in q_lower for k in ("customer", "tier", "industry")):
        sql_str = "SELECT id, name, tier, industry, status FROM customers"
    elif any(k in q_lower for k in ("team", "lead", "slack")):
        sql_str = "SELECT id, name, lead, slack_channel, description FROM teams"
    else:
        sql_str = "SELECT id, name, tier, repo_url FROM services WHERE id = :service_id"
        params["service_id"] = service_id

    results = execute_governed_sql(
        sql_str=sql_str,
        params=params,
        sub_question_id=sub_q_id,
    )
    return results, sql_str


def execute_retrieval(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """Execute retrieval node across all active sub-questions (F5, F6, F7, F8).

    Dispatches sub-questions to corresponding stores (Graph, SQL, Hybrid, Vector),
    records telemetry query timings, and captures any store failures gracefully.

    Args:
        state: Shared ResearchState or state dictionary.

    Returns:
        Partial state update dict for LangGraph StateGraph.
    """
    session_id = str(
        _get_field(state, "session_id", "default-session") or "default-session"
    )
    sub_questions = list(_get_field(state, "sub_questions", []) or [])
    time_range = dict(_get_field(state, "time_range", {}) or {})
    entity = _get_field(state, "entity")
    existing_errors = list(_get_field(state, "errors", []) or [])
    existing_evidence = list(_get_field(state, "evidence", []) or [])
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()
    new_evidence: list[Evidence] = []
    new_errors: list[str] = []
    evidence_counts_by_sq: dict[str, int] = {}
    strategies_executed: set[str] = set()

    # Outer telemetry context for node execution
    try:
        cm = tracer.node(session_id=session_id, node_name="execute_retrieval")
    except Exception:  # noqa: BLE001
        cm = None

    def _run_retrievals() -> None:
        for idx, sq in enumerate(sub_questions):
            sq_id = sq.get("id", f"sq{idx + 1}")
            question = sq.get("question", "")
            strategy = sq.get("strategy", "vector")
            target = sq.get("target_entity") or entity
            strategies_executed.add(strategy)

            try:
                if strategy == "graph":
                    ev_items, query_desc = _execute_graph_sub_question(
                        sub_q_id=sq_id,
                        question=question,
                        target_entity=target,
                    )
                elif strategy == "sql":
                    ev_items, query_desc = _execute_sql_sub_question(
                        sub_q_id=sq_id,
                        question=question,
                        target_entity=target,
                        time_range=time_range,
                    )
                elif strategy == "hybrid":
                    ev_items = retrieve_hybrid(
                        query=question,
                        sub_question_id=sq_id,
                        top_n_final=3,
                    )
                    query_desc = f"hybrid:{question[:60]}"
                else:  # vector
                    ev_items = retrieve_hybrid(
                        query=question,
                        sub_question_id=sq_id,
                        top_n_final=3,
                    )
                    query_desc = f"vector:{question[:60]}"

                new_evidence.extend(ev_items)
                evidence_counts_by_sq[sq_id] = len(ev_items)

                # Safe telemetry recording
                try:
                    tracer.record_query(
                        session_id=session_id,
                        store_type=strategy,
                        query_text=query_desc,
                        result_count=len(ev_items),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed recording query telemetry: %s", exc)

            except Exception as exc:  # noqa: BLE001
                # Claude.md §7.3: Store failure records an error; never crashes workflow
                err_msg = f"Store retrieval failed for {sq_id} ({strategy}): {exc}"
                logger.warning(err_msg)
                new_errors.append(err_msg)
                evidence_counts_by_sq[sq_id] = 0

    if cm is not None:
        try:
            with cm as ctx:
                _run_retrievals()
                if ctx and hasattr(ctx, "payload"):
                    ctx.payload.update(
                        {
                            "retrieved_evidence_total": len(new_evidence),
                            "sub_questions_executed": len(sub_questions),
                            "strategies": list(strategies_executed),
                            "errors_count": len(new_errors),
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telemetry context failed in execute_retrieval: %s", exc)
    else:
        _run_retrievals()

    combined_evidence = existing_evidence + new_evidence
    combined_errors = existing_errors + new_errors

    return {
        "current_node": "execute_retrieval",
        "evidence": combined_evidence,
        "errors": combined_errors,
        "metadata": {
            **existing_meta,
            "retrieved_evidence_count": len(combined_evidence),
            "evidence_by_sub_question": evidence_counts_by_sq,
            "retrieval_errors": new_errors,
        },
    }


# LangGraph node alias
execute_retrieval_node = execute_retrieval
