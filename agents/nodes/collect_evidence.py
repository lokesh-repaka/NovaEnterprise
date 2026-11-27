"""Evidence collection and deduplication node for LangGraph workflow (P9-5, F9, Claude.md §3.1, §5, §7.3).

Primary Responsibilities:
- Aggregate newly retrieved evidence with existing state evidence.
- Normalize heterogeneous evidence formats (raw dicts or Evidence models) into canonical Evidence schemas.
- Deduplicate evidence by (source_type, locator), preserving the highest score across identical locators.
- Preserve citation locators across Document, SQL, and Graph stores.
- Record telemetry via tracer.node("collect_evidence") with zero-crash resilience.
- Return partial state dictionary updating: evidence, metadata, and current_node.
"""

from __future__ import annotations

from typing import Any

from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from backend.app.schemas.common import Evidence
from rag.evidence import deduplicate_evidence, generate_evidence_id

logger = get_logger("agents.nodes.collect_evidence")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def collect_evidence(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to normalize, merge, and deduplicate retrieved evidence records.

    Args:
        state: ResearchState or dictionary representation containing evidence.

    Returns:
        Partial state dictionary with normalized and deduplicated evidence list.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    raw_evidence_list = _get_field(state, "evidence", []) or []
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()

    def _execute_collection() -> dict[str, Any]:
        normalized_items: list[Evidence] = []
        raw_count = len(raw_evidence_list)

        for item in raw_evidence_list:
            if isinstance(item, Evidence):
                normalized_items.append(item)
            elif isinstance(item, dict):
                try:
                    d = dict(item)
                    if "id" not in d:
                        sub_q = str(d.get("sub_question_id", "sq1"))
                        src = str(d.get("source_type", "document"))
                        loc = str(d.get("locator", "unknown"))
                        cnt = str(d.get("content", ""))
                        d["id"] = generate_evidence_id(sub_q, src, loc, cnt)
                    normalized_items.append(Evidence(**d))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Skipping invalid evidence record in session %s: %s",
                        session_id,
                        exc,
                    )
            else:
                logger.warning(
                    "Unexpected item type in evidence list for session %s: %s",
                    session_id,
                    type(item),
                )

        deduped = deduplicate_evidence(normalized_items)
        deduped_count = raw_count - len(deduped)

        logger.info(
            "Evidence collected for session %s: %d total raw -> %d deduplicated",
            session_id,
            raw_count,
            len(deduped),
        )

        updated_metadata = {
            **existing_meta,
            "evidence_count": len(deduped),
            "deduplicated_count": deduped_count,
        }

        return {
            "evidence": deduped,
            "metadata": updated_metadata,
            "current_node": "collect_evidence",
        }

    try:
        with tracer.node(session_id, "collect_evidence"):
            return _execute_collection()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tracer error in collect_evidence node for session %s (continuing): %s",
            session_id,
            exc,
        )
        return _execute_collection()


# Canonical alias for LangGraph registration
collect_evidence_node = collect_evidence

__all__ = ["collect_evidence", "collect_evidence_node"]
