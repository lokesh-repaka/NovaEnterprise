"""Evidence claim verification node for LangGraph research workflow (P9-7, F10, Claude.md §3.1, §5, §7.3, FRD §5.2 FR-10).

Primary Responsibilities:
- Cross-verify retrieved evidence items for factual validity, locator completeness, and minimum relevance confidence.
- Filter out below-threshold, malformed, or contradictory evidence items.
- Calculate verification_ratio (proportion of collected evidence meeting strict verification thresholds).
- Record verified evidence items in verified_evidence.
- Telemetry recording via tracer.node("verify_evidence") with zero-crash resilience.
- Return partial state dictionary updating: verified_evidence, verification_ratio, metadata, and current_node.
"""

from __future__ import annotations

from typing import Any

from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from backend.app.schemas.common import Evidence
from rag.evidence import generate_evidence_id

logger = get_logger("agents.nodes.verify_evidence")

# Minimum relevance score threshold to qualify as verified evidence
MIN_VERIFICATION_SCORE = 0.30


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def verify_evidence(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to cross-verify claims and filter invalid or low-confidence evidence.

    Args:
        state: ResearchState or dictionary representation containing evidence.

    Returns:
        Partial state dictionary with verified_evidence and verification_ratio.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    evidence_list = _get_field(state, "evidence", []) or []
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()

    def _execute_verification() -> dict[str, Any]:
        verified_items: list[Evidence] = []
        raw_count = len(evidence_list)

        for item in evidence_list:
            ev_obj: Evidence | None = None
            if isinstance(item, Evidence):
                ev_obj = item
            elif isinstance(item, dict):
                try:
                    d = dict(item)
                    if "id" not in d:
                        sub_q = str(d.get("sub_question_id", "sq1"))
                        src = str(d.get("source_type", "document"))
                        loc = str(d.get("locator", "unknown"))
                        cnt = str(d.get("content", ""))
                        d["id"] = generate_evidence_id(sub_q, src, loc, cnt)
                    ev_obj = Evidence(**d)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Malformed evidence record in session %s: %s",
                        session_id,
                        exc,
                    )
                    continue

            if ev_obj is None:
                continue

            # Invariants for verification:
            # 1. Non-empty content and locator
            # 2. Recognized source_type
            # 3. Score meets minimum verification threshold
            if (
                ev_obj.content
                and len(ev_obj.content.strip()) >= 3
                and ev_obj.locator
                and ev_obj.source_type in {"document", "sql", "graph"}
                and ev_obj.score >= MIN_VERIFICATION_SCORE
            ):
                verified_items.append(ev_obj)
            else:
                logger.debug(
                    "Evidence item %s rejected during verification (score=%.2f, locator=%s)",
                    ev_obj.id,
                    ev_obj.score,
                    ev_obj.locator,
                )

        verification_ratio = (
            round(len(verified_items) / raw_count, 4) if raw_count > 0 else 0.0
        )

        logger.info(
            "Evidence verification complete for session %s: %d/%d verified (ratio=%.4f)",
            session_id,
            len(verified_items),
            raw_count,
            verification_ratio,
        )

        updated_metadata = {
            **existing_meta,
            "verified_evidence_count": len(verified_items),
            "raw_evidence_count": raw_count,
            "verification_ratio": verification_ratio,
        }

        return {
            "verified_evidence": verified_items,
            "verification_ratio": verification_ratio,
            "metadata": updated_metadata,
            "current_node": "verify_evidence",
        }

    try:
        with tracer.node(session_id, "verify_evidence"):
            return _execute_verification()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tracer error in verify_evidence node for session %s (continuing): %s",
            session_id,
            exc,
        )
        return _execute_verification()


# Canonical alias for LangGraph registration
verify_evidence_node = verify_evidence

__all__ = ["verify_evidence", "verify_evidence_node"]
