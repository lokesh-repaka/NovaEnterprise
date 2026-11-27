"""Retrieval routing node for LangGraph research workflow (P9-4, F5, Claude.md §3.1, §5, §7.3).

Primary Responsibilities:
- Assign or validate retrieval strategies ('vector', 'sql', 'graph', 'hybrid') for each sub-question.
- Enforce deterministic routing floors via enforce_routing_floor() from agents.rules.
- Enforce simple complexity invariant: strategies_used contains only 'vector' (no SQL, no Cypher).
- Wrap execution in tracer.node(...) without allowing telemetry to crash the workflow.
- Return partial state dictionary updating: sub_questions, strategies_used, and metadata.
"""

from __future__ import annotations

from typing import Any

from agents.rules import (
    ComplexityLevel,
    SubQuestion,
    detect_retrieval_strategy,
    enforce_routing_floor,
)
from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer

logger = get_logger("agents.nodes.route_retrieval")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def route_retrieval(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """Execute retrieval routing node (F5).

    Evaluates each sub-question and assigns or confirms its retrieval strategy,
    enforcing deterministic policy constraints and routing floors.

    Args:
        state: Shared ResearchState or state dictionary.

    Returns:
        Partial state update dict for LangGraph StateGraph.
    """
    session_id = str(
        _get_field(state, "session_id", "default-session") or "default-session"
    )
    raw_sub_questions = list(_get_field(state, "sub_questions", []) or [])
    raw_complexity = _get_field(state, "complexity")
    complexity: ComplexityLevel = (
        raw_complexity
        if raw_complexity in ("simple", "moderate", "complex")
        else "complex"
    )
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    routed_sub_questions: list[SubQuestion] = []
    routing_decisions: list[dict[str, Any]] = []

    for idx, sq_data in enumerate(raw_sub_questions):
        sq_id = sq_data.get("id", f"sq{idx + 1}")
        question_text = sq_data.get("question", "")
        current_strategy = sq_data.get("strategy") or detect_retrieval_strategy(
            question_text
        )
        target_entity = sq_data.get("target_entity")

        unfloored = SubQuestion(
            id=sq_id,
            question=question_text,
            strategy=current_strategy,
            target_entity=target_entity,
            rule_applied=sq_data.get("rule_applied"),
            rationale=sq_data.get("rationale"),
            metadata=sq_data.get("metadata", {}),
        )

        # Enforce deterministic routing floor (Claude.md §7.2, §18.4)
        floored = enforce_routing_floor(unfloored, overall_complexity=complexity)

        routed_sub_questions.append(floored)
        routing_decisions.append(
            {
                "sub_question_id": floored.id,
                "original_strategy": current_strategy,
                "enforced_strategy": floored.strategy,
                "rule_applied": floored.rule_applied or "RULE_ROUTED_DEFAULT",
                "overridden": current_strategy != floored.strategy,
            }
        )

    # Compile strategies_used list
    if complexity == "simple":
        # Strictly vector only per Claude.md §7.3
        strategies_used = ["vector"]
    else:
        # Preserve discovery order
        seen_strategies: set[str] = set()
        strategies_used = []
        for sq in routed_sub_questions:
            if sq.strategy not in seen_strategies:
                seen_strategies.add(sq.strategy)
                strategies_used.append(sq.strategy)

    # Telemetry wrapping with zero-crash guarantee
    tracer = get_tracer()
    try:
        with tracer.node(session_id=session_id, node_name="route_retrieval") as ctx:
            if ctx and hasattr(ctx, "payload"):
                ctx.payload.update(
                    {
                        "strategies_used": strategies_used,
                        "sub_questions_count": len(routed_sub_questions),
                        "routing_decisions": routing_decisions,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telemetry error in route_retrieval (session=%s): %s",
            session_id,
            exc,
        )

    return {
        "current_node": "route_retrieval",
        "sub_questions": [sq.model_dump() for sq in routed_sub_questions],
        "strategies_used": strategies_used,
        "metadata": {
            **existing_meta,
            "strategies_used": strategies_used,
            "routing_decisions": routing_decisions,
        },
    }


# LangGraph node alias
route_retrieval_node = route_retrieval
