"""Citation verification and integrity node for LangGraph research workflow (P9-8, F12, Claude.md §3.1, §5, §7.3, FRD §5.2 FR-12, LLD §4.3).

Primary Responsibilities:
- Mathematical confirmation that all [n] citation tokens in the synthesized answer map to valid evidence records.
- Detect, report, and strip unresolvable citation tokens from the answer text to eliminate hallucinated references.
- Filter the citations array to retain only verified citation objects.
- Record unresolved_citations list and set citations_verified boolean.
- Telemetry recording via tracer.node("verify_citations") with zero-crash resilience.
- Return partial state dictionary updating: answer, citations, unresolved_citations, citations_verified, metadata, and current_node.
"""

from __future__ import annotations

import re
from typing import Any

from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer

logger = get_logger("agents.nodes.verify_citations")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def verify_citations(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to verify that all citation markers in the answer map to existing evidence.

    Args:
        state: ResearchState or dictionary representation containing answer and evidence.

    Returns:
        Partial state dictionary with sanitized answer and verification status.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    answer_text = str(_get_field(state, "answer", "") or "")
    evidence_list = (
        _get_field(state, "verified_evidence") or _get_field(state, "evidence") or []
    )
    citations_list = list(_get_field(state, "citations", []) or [])
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()

    def _execute_citation_verification() -> dict[str, Any]:
        # Extract all [n] integer citation tokens from the synthesized answer
        found_tokens = [int(m) for m in re.findall(r"\[(\d+)\]", answer_text)]
        valid_indices = set(range(1, len(evidence_list) + 1))

        # Check for citation tokens pointing beyond available evidence records
        unresolved = [tok for tok in found_tokens if tok not in valid_indices]

        # Strip or sanitize unresolvable citation markers if any exist
        sanitized_answer = answer_text
        for bad_token in unresolved:
            sanitized_answer = sanitized_answer.replace(f"[{bad_token}]", "")

        # Clean up any leftover double spaces
        sanitized_answer = re.sub(r" +", " ", sanitized_answer).strip()

        # Retain only verified citations whose ID maps to valid evidence and was not stripped
        verified_citations: list[dict[str, Any]] = []
        for cit in citations_list:
            if isinstance(cit, dict):
                c_id = cit.get("citation_id")
                if c_id in valid_indices and c_id not in unresolved:
                    verified_citations.append(cit)
            else:
                c_id = getattr(cit, "citation_id", None)
                if c_id in valid_indices and c_id not in unresolved:
                    verified_citations.append(
                        cit.model_dump() if hasattr(cit, "model_dump") else cit
                    )

        citations_verified = len(unresolved) == 0

        logger.info(
            "Citation verification complete for session %s: %d tokens found, %d unresolved, verified=%s",
            session_id,
            len(found_tokens),
            len(unresolved),
            citations_verified,
        )

        updated_metadata = {
            **existing_meta,
            "found_citation_tokens": len(found_tokens),
            "unresolved_citations": unresolved,
            "citations_verified": citations_verified,
            "verified_citations_count": len(verified_citations),
        }

        return {
            "answer": sanitized_answer,
            "citations": verified_citations,
            "unresolved_citations": unresolved,
            "citations_verified": citations_verified,
            "metadata": updated_metadata,
            "current_node": "verify_citations",
        }

    try:
        with tracer.node(session_id, "verify_citations"):
            return _execute_citation_verification()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tracer error in verify_citations node for session %s (continuing): %s",
            session_id,
            exc,
        )
        return _execute_citation_verification()


# Canonical alias for LangGraph registration
verify_citations_node = verify_citations

__all__ = ["verify_citations", "verify_citations_node"]
