"""Query analysis node for LangGraph research workflow (P9-2, F2, Claude.md §3.1, §7.3).

Primary Responsibilities:
- Extract query intent, domain entities, and temporal filters from user question.
- Map temporal filters against enterprise fiscal calendar via OrganizationalMemoryLoader.
- Detect store modality requirements (SQL, Graph, Documents, Relationships, Aggregation).
- Wrap execution in tracer.node(...) without allowing telemetry to crash the workflow.
- Return partial state dictionary updating: intent, entity, time_range, and metadata.
"""

from __future__ import annotations

from typing import Any

from agents.rules import AnalysisResult, analyze_query_rules
from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from memory.org_loader import OrganizationalMemoryLoader

logger = get_logger("agents.nodes.analyze_query")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def analyze_query(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """Execute query analysis node (F2).

    Parses question into intent, target enterprise entity, temporal date bounds,
    and required store retrieval modalities.

    Args:
        state: Shared ResearchState or state dictionary.

    Returns:
        Partial state update dict for LangGraph StateGraph.
    """
    question = str(_get_field(state, "question", "") or "").strip()
    session_id = str(
        _get_field(state, "session_id", "default-session") or "default-session"
    )
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    # 1. Deterministic rule-based analysis floor
    analysis: AnalysisResult = analyze_query_rules(question)

    # 2. Fiscal calendar and temporal date bound resolution
    time_range_dict: dict[str, str] = {}
    if analysis.time_range:
        try:
            org_loader = OrganizationalMemoryLoader()
            calendar = org_loader.get_fiscal_calendar()
            raw_tr = analysis.time_range.strip()
            norm_tr = raw_tr.lower().replace(" ", "_")

            if norm_tr in {"last_quarter", "lastquarter", "previous_quarter"}:
                target_code = calendar.last_quarter
            elif norm_tr in {"current_quarter", "currentquarter", "this_quarter"}:
                target_code = calendar.current_quarter
            else:
                target_code = raw_tr.upper()

            quarter = calendar.quarters.get(target_code)
            if quarter:
                time_range_dict = {
                    "start_date": quarter.start_date,
                    "end_date": quarter.end_date,
                    "quarter": target_code,
                    "quarter_name": quarter.name,
                }
            else:
                time_range_dict = {"raw": analysis.time_range}
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed resolving quarter '%s' via organizational memory: %s",
                analysis.time_range,
                exc,
            )
            time_range_dict = {"raw": analysis.time_range}

    # 3. Determine primary entity
    primary_entity = analysis.entities[0] if analysis.entities else None

    # 4. Telemetry wrapping with zero-crash guarantee
    tracer = get_tracer()
    try:
        with tracer.node(session_id=session_id, node_name="analyze_query") as ctx:
            if ctx and hasattr(ctx, "payload"):
                ctx.payload.update(
                    {
                        "intent": analysis.intent,
                        "entity": primary_entity,
                        "entities_count": len(analysis.entities),
                        "time_range": time_range_dict,
                        "needs_sql": analysis.needs_sql,
                        "needs_graph": analysis.needs_graph,
                        "needs_documents": analysis.needs_documents,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telemetry error in analyze_query (session=%s): %s",
            session_id,
            exc,
        )

    # 5. Return partial state dictionary
    return {
        "current_node": "analyze_query",
        "intent": analysis.intent,
        "entity": primary_entity,
        "time_range": time_range_dict,
        "metadata": {
            **existing_meta,
            "entities": analysis.entities,
            "needs_sql": analysis.needs_sql,
            "needs_graph": analysis.needs_graph,
            "needs_documents": analysis.needs_documents,
            "needs_relationships": analysis.needs_relationships,
            "needs_aggregation": analysis.needs_aggregation,
            "time_range_raw": analysis.time_range,
        },
    }


# LangGraph node alias
analyze_query_node = analyze_query
