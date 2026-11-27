"""Bounded corrective retrieval loop node for LangGraph research workflow (P9-6, F9, Claude.md §3.1, §5, §7.3, FRD §5.2).

Primary Responsibilities:
- Evaluate missing_facets (sub-question IDs lacking adequate evidence).
- Reformulate sub-queries using domain term expansion and synonym broadening (Alternative Flow 4a).
- Re-execute multi-store lookups (Vector, Hybrid, Graph, SQL) for the unbacked facets.
- Increment corrective_rounds (enforcing MAX_CORRECTIVE_ROUNDS = 1 loop boundary invariant).
- Append newly retrieved evidence into state and mark needs_retry = False upon completion.
- Telemetry recording via tracer.node("corrective_retrieval") with zero-crash resilience.
- Return partial state dictionary updating: evidence, sub_questions, corrective_rounds, needs_retry, metadata, and current_node.
"""

from __future__ import annotations

from typing import Any

from agents.nodes.execute_retrieval import (
    _execute_graph_sub_question,
    _execute_sql_sub_question,
)
from agents.state import ResearchState
from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from backend.app.schemas.common import Evidence
from rag.retriever import retrieve_hybrid

logger = get_logger("agents.nodes.corrective_retrieval")

# Domain synonym dictionary for query expansion during corrective cycles
_SYNONYM_EXPANSIONS: dict[str, list[str]] = {
    "outage": ["incident", "postmortem", "breakdown", "downtime", "failure", "sev1"],
    "incident": ["outage", "postmortem", "root cause", "mitigation", "timeline"],
    "remediation": [
        "mitigation",
        "actions",
        "fix",
        "resolution",
        "prevention",
        "pgbouncer",
    ],
    "action": ["mitigation", "steps", "remediation", "resolution"],
    "actions": ["mitigation", "steps", "remediation", "resolution"],
    "failure": ["incident", "outage", "error", "timeout", "crash"],
    "revenue": ["loss", "financial", "impact", "customers", "cost"],
    "impact": ["revenue", "financial", "customers", "outage"],
    "performance": ["latency", "throughput", "saturation", "bottleneck"],
    "dependencies": ["architecture", "topology", "services", "database"],
    "team": ["owner", "ownership", "engineering", "lead"],
}


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def reformulate_query(query: str, target_entity: str | None = None) -> str:
    """Reformulate a sub-question query with broadened search terms and domain synonyms.

    Appends relevant synonyms to increase hybrid retrieval recall without losing original intent.
    """
    query_lower = query.lower()
    expansion_terms: list[str] = []

    for keyword, synonyms in _SYNONYM_EXPANSIONS.items():
        if keyword in query_lower:
            for syn in synonyms:
                if syn not in query_lower and syn not in expansion_terms:
                    expansion_terms.append(syn)

    # If no specific synonym matched, apply default incident/mitigation terminology
    if not expansion_terms:
        expansion_terms = ["incident", "mitigation", "root cause"]

    # Prepend target entity if not present
    entity_prefix = (
        f"[{target_entity}] "
        if target_entity and target_entity.lower() not in query_lower
        else ""
    )

    selected_synonyms = expansion_terms[:3]
    suffix = f" ({' OR '.join(selected_synonyms)})" if selected_synonyms else ""
    return f"{entity_prefix}{query}{suffix}"


def corrective_retrieval(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to execute bounded corrective retrieval for unbacked sub-questions.

    Args:
        state: ResearchState or dictionary representation.

    Returns:
        Partial state dictionary with newly retrieved evidence, incremented corrective_rounds,
        and updated needs_retry flag.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    missing_facets: list[str] = list(_get_field(state, "missing_facets", []) or [])
    sub_questions: list[dict[str, Any]] = list(
        _get_field(state, "sub_questions", []) or []
    )
    existing_evidence: list[Evidence | dict[str, Any]] = list(
        _get_field(state, "evidence", []) or []
    )
    corrective_rounds = int(_get_field(state, "corrective_rounds", 0) or 0)
    entity = _get_field(state, "entity")
    time_range = dict(_get_field(state, "time_range", {}) or {})
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    settings = get_settings()
    max_rounds = getattr(settings, "max_corrective_rounds", 1)
    tracer = get_tracer()

    def _execute_corrective() -> dict[str, Any]:
        # Bounded loop invariant (Claude.md §7.3): hard limit at MAX_CORRECTIVE_ROUNDS
        if corrective_rounds >= max_rounds:
            logger.info(
                "Session %s reached max corrective rounds (%d/%d); skipping corrective retrieval",
                session_id,
                corrective_rounds,
                max_rounds,
            )
            return {
                "corrective_rounds": corrective_rounds,
                "needs_retry": False,
                "metadata": {
                    **existing_meta,
                    "skipped_max_rounds": True,
                    "corrective_rounds": corrective_rounds,
                },
                "current_node": "corrective_retrieval",
            }

        new_evidence: list[Evidence] = []
        updated_sub_questions: list[dict[str, Any]] = []
        reformulated_ids: list[str] = []

        # Find matching sub-questions for all missing facets
        for sq in sub_questions:
            sq_copy = dict(sq)
            sq_id = str(sq_copy.get("id", ""))

            if sq_id in missing_facets:
                original_q = sq_copy.get("question", "")
                strategy = sq_copy.get("strategy", "vector")
                target = sq_copy.get("target_entity") or entity

                reformulated_q = reformulate_query(original_q, target_entity=target)
                sq_copy["question"] = reformulated_q
                sq_copy["original_question"] = original_q
                sq_copy["reformulated"] = True
                reformulated_ids.append(sq_id)

                # Re-execute retrieval with reformulated query
                ev_items: list[Evidence] = []
                query_desc = ""

                try:
                    if strategy == "graph":
                        ev_items, query_desc = _execute_graph_sub_question(
                            sub_q_id=sq_id,
                            question=reformulated_q,
                            target_entity=target,
                        )
                    elif strategy == "sql":
                        ev_items, query_desc = _execute_sql_sub_question(
                            sub_q_id=sq_id,
                            question=reformulated_q,
                            target_entity=target,
                            time_range=time_range,
                        )
                    else:
                        ev_items = retrieve_hybrid(
                            query=reformulated_q,
                            sub_question_id=sq_id,
                            top_n_final=3,
                        )
                        query_desc = f"corrective_hybrid:{reformulated_q[:60]}"

                    new_evidence.extend(ev_items)

                    # Telemetry recording for the corrective query
                    try:
                        tracer.record_query(
                            session_id=session_id,
                            store_type=f"corrective_{strategy}",
                            query_text=query_desc,
                            result_count=len(ev_items),
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(
                            "Failed recording corrective query telemetry: %s", exc
                        )

                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Corrective retrieval failed for facet %s (%s): %s",
                        sq_id,
                        strategy,
                        exc,
                    )

            updated_sub_questions.append(sq_copy)

        next_rounds = corrective_rounds + 1
        combined_evidence = existing_evidence + new_evidence

        logger.info(
            "Corrective retrieval complete for session %s: round %d/%d, reformulated %d facets, retrieved %d items",
            session_id,
            next_rounds,
            max_rounds,
            len(reformulated_ids),
            len(new_evidence),
        )

        updated_metadata = {
            **existing_meta,
            "corrective_iterations": next_rounds,
            "reformulated_facets": reformulated_ids,
            "corrective_evidence_retrieved": len(new_evidence),
        }

        return {
            "evidence": combined_evidence,
            "sub_questions": updated_sub_questions,
            "corrective_rounds": next_rounds,
            "needs_retry": False,
            "metadata": updated_metadata,
            "current_node": "corrective_retrieval",
        }

    try:
        with tracer.node(session_id, "corrective_retrieval"):
            return _execute_corrective()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tracer error in corrective_retrieval node for session %s (continuing): %s",
            session_id,
            exc,
        )
        return _execute_corrective()


# Canonical alias for LangGraph registration
corrective_retrieval_node = corrective_retrieval

__all__ = [
    "corrective_retrieval",
    "corrective_retrieval_node",
    "reformulate_query",
]
