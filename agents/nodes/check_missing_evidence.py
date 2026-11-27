"""Missing evidence evaluation node for LangGraph research workflow (P9-5, F9, Claude.md §3.1, §7.3, FRD §5.2).

Primary Responsibilities:
- Evaluate sub-question coverage: verify each decomposed sub-question has >= 1 supporting evidence item.
- Identify unbacked sub-questions and populate missing_facets.
- Enforce the bounded corrective loop invariant:
  - If missing_facets is non-empty and corrective_rounds < MAX_CORRECTIVE_ROUNDS (default 1):
    sets needs_retry = True (triggers corrective_retrieval in P9-6).
  - If corrective_rounds >= MAX_CORRECTIVE_ROUNDS or all facets covered:
    sets needs_retry = False (terminates loop and proceeds to evidence verification in P9-7).
- Telemetry recording via tracer.node("check_missing_evidence") with zero-crash resilience.
- Return partial state dictionary updating: missing_facets, needs_retry, metadata, and current_node.
"""

from __future__ import annotations

from typing import Any

from agents.state import ResearchState
from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from backend.app.schemas.common import Evidence

logger = get_logger("agents.nodes.check_missing_evidence")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def check_missing_evidence(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to assess sub-question evidence coverage and bound the corrective loop.

    Args:
        state: ResearchState or dictionary representation containing evidence and sub_questions.

    Returns:
        Partial state dictionary with missing_facets, needs_retry flag, and metadata.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    sub_questions = _get_field(state, "sub_questions", []) or []
    evidence_list = _get_field(state, "evidence", []) or []
    corrective_rounds = int(_get_field(state, "corrective_rounds", 0) or 0)
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()
    settings = get_settings()
    max_rounds = getattr(settings, "max_corrective_rounds", 1)

    def _execute_check() -> dict[str, Any]:
        # Collect all sub_question_ids present in the gathered evidence
        covered_ids: set[str] = set()
        for item in evidence_list:
            if isinstance(item, Evidence):
                if item.sub_question_id:
                    covered_ids.add(str(item.sub_question_id))
            elif isinstance(item, dict):
                sq_id = item.get("sub_question_id")
                if sq_id:
                    covered_ids.add(str(sq_id))

        missing_facets: list[str] = []

        if sub_questions:
            for sq in sub_questions:
                if isinstance(sq, dict):
                    sq_id = str(sq.get("id", ""))
                else:
                    sq_id = str(getattr(sq, "id", ""))
                if sq_id and sq_id not in covered_ids:
                    missing_facets.append(sq_id)
        else:
            # Single undecomposed query without sub-questions:
            # If no evidence was retrieved, flag root query as missing
            if not evidence_list:
                missing_facets.append("sq1")

        # Bounded loop invariant (Claude.md §7.3, FRD §5.2 FR-09)
        if missing_facets and corrective_rounds < max_rounds:
            needs_retry = True
        else:
            needs_retry = False

        logger.info(
            "Missing evidence check for session %s: missing=%s, rounds=%d/%d, needs_retry=%s",
            session_id,
            missing_facets,
            corrective_rounds,
            max_rounds,
            needs_retry,
        )

        updated_metadata = {
            **existing_meta,
            "missing_facets_count": len(missing_facets),
            "needs_retry": needs_retry,
            "corrective_rounds": corrective_rounds,
        }

        return {
            "missing_facets": missing_facets,
            "needs_retry": needs_retry,
            "metadata": updated_metadata,
            "current_node": "check_missing_evidence",
        }

    try:
        with tracer.node(session_id, "check_missing_evidence"):
            return _execute_check()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tracer error in check_missing_evidence node for session %s (continuing): %s",
            session_id,
            exc,
        )
        return _execute_check()


# Canonical alias for LangGraph registration
check_missing_evidence_node = check_missing_evidence

__all__ = ["check_missing_evidence", "check_missing_evidence_node"]
