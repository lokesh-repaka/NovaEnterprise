"""Memory recall node for LangGraph research workflow (P10-1, F15, Claude.md §3.1, §7.3, §7.4).

Primary Responsibilities:
- Node 1 in the 13-node research workflow.
- Ingest session_id and user_id from incoming state.
- Query MemoryService.recall(session_id, user_id) to retrieve unified 4-scope context snapshot:
  - Working memory state
  - Episodic session history
  - Semantic profile & user insights
  - Organizational memory (fiscal calendars, tier definitions, service owners)
- Hydrate metadata with memory metrics and status without crashing the workflow.
- Wrap execution in tracer.node(session_id, "recall_memory") with zero-crash telemetry resilience.
- Return partial state dictionary updating: current_node and metadata.
"""

from __future__ import annotations

from typing import Any

from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer
from memory.memory_service import get_memory_service

logger = get_logger("agents.nodes.recall_memory")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def recall_memory(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """LangGraph node to recall multi-scope memory context and hydrate research state metadata.

    Args:
        state: ResearchState or dictionary representation containing session_id and user_id.

    Returns:
        Partial state dictionary updating current_node and metadata.
    """
    session_id = str(_get_field(state, "session_id", "session-unknown"))
    user_id = _get_field(state, "user_id")
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    tracer = get_tracer()

    def _execute_recall() -> dict[str, Any]:
        episodic_count = 0
        semantic_count = 0
        working_findings = 0

        try:
            mem_service = get_memory_service()
            context = mem_service.recall(session_id=session_id, user_id=user_id)
            episodic_count = len(context.episodic)
            semantic_count = len(context.semantic)
            working_findings = len(context.working.findings)
            logger.info(
                "Recalled memory for session '%s' (user: %s): %d episodic, %d semantic, %d working findings",
                session_id,
                user_id,
                episodic_count,
                semantic_count,
                working_findings,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Memory recall failed non-fatally for session '%s': %s",
                session_id,
                exc,
            )

        updated_metadata = {
            **existing_meta,
            "memory_recalled": True,
            "episodic_history_count": episodic_count,
            "semantic_insights_count": semantic_count,
            "working_findings_count": working_findings,
        }

        return {
            "current_node": "recall_memory",
            "metadata": updated_metadata,
        }

    cm = None
    try:
        cm = tracer.node(session_id, "recall_memory")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed opening telemetry span: %s", exc)

    if cm is not None:
        try:
            with cm as ctx:
                result = _execute_recall()
                if ctx and hasattr(ctx, "payload"):
                    ctx.payload.update(
                        {
                            "session_id": session_id,
                            "user_id": user_id,
                            "memory_recalled": True,
                        }
                    )
                return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telemetry context failed in recall_memory: %s", exc)
            return _execute_recall()
    else:
        return _execute_recall()


# LangGraph node alias
recall_memory_node = recall_memory
