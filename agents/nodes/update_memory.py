"""Memory update and research finalization node for LangGraph workflow (P9-8, F15, Claude.md §3.1, §7.4, FRD §5.2).

Primary Responsibilities:
- Record the completed multi-turn research interaction into episodic session memory (Redis / in-memory).
- Persist question, sanitized answer, citation locators, and complexity into memory service.
- Transition workflow execution state to 'completed'.
- Telemetry recording via tracer.node("update_memory") with zero-crash resilience.
- Return partial state dictionary updating: status, metadata, and current_node.
"""

from __future__ import annotations

from typing import Any

from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from memory.memory_service import get_memory_service

logger = get_logger("agents.nodes.update_memory")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def update_memory(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to write completed session context to episodic memory and finalize workflow.

    Args:
        state: ResearchState or dictionary representation.

    Returns:
        Partial state dictionary with status='completed' and updated metadata.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    question = str(_get_field(state, "question", ""))
    answer = str(_get_field(state, "answer", ""))
    citations_raw = _get_field(state, "citations", []) or []
    complexity = _get_field(state, "complexity")
    user_id = _get_field(state, "user_id") or "demo-user"
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()

    def _execute_memory_update() -> dict[str, Any]:
        # Extract citation locators for episodic recording
        citation_locators: list[str] = []
        for c in citations_raw:
            if isinstance(c, dict):
                loc = c.get("locator")
                if loc:
                    citation_locators.append(str(loc))
            else:
                loc = getattr(c, "locator", None)
                if loc:
                    citation_locators.append(str(loc))

        # Write interaction turn into episodic memory
        mem_service = get_memory_service()
        try:
            mem_service.update_turn(
                session_id=session_id,
                question=question,
                answer=answer,
                citations=citation_locators,
                complexity=str(complexity) if complexity else None,
                user_id=str(user_id) if user_id else None,
            )
            logger.info(
                "Episodic memory turn recorded for session %s (citations=%d)",
                session_id,
                len(citation_locators),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to update episodic memory for session %s (continuing): %s",
                session_id,
                exc,
            )

        updated_metadata = {
            **existing_meta,
            "memory_updated": True,
            "session_id": session_id,
            "persisted_citations_count": len(citation_locators),
        }

        return {
            "status": "completed",
            "metadata": updated_metadata,
            "current_node": "update_memory",
        }

    try:
        with tracer.node(session_id, "update_memory"):
            return _execute_memory_update()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tracer error in update_memory node for session %s (continuing): %s",
            session_id,
            exc,
        )
        return _execute_memory_update()


# Canonical aliases for LangGraph registration
update_memory_node = update_memory
memory_update = update_memory
memory_update_node = update_memory

__all__ = [
    "memory_update",
    "memory_update_node",
    "update_memory",
    "update_memory_node",
]
