"""Complexity assessment node for LangGraph research workflow (P9-2, F3, Claude.md §3.1, §7.3).

Primary Responsibilities:
- Classify question complexity as 'simple', 'moderate', or 'complex' using deterministic rules.
- Enforce strict complexity-driven workflow shape constraints:
    - simple: exactly 1 sub-question, vector only, no SQL, no Cypher.
    - moderate: 1–2 sub-questions, single-store or single-relationship.
    - complex: <= MAX_SUBQUESTIONS (default 4), cross-domain joins (SQL + Graph + Document).
- Wrap execution in tracer.node(...) without allowing telemetry to crash the workflow.
- Return partial state dictionary updating: complexity and metadata.
"""

from __future__ import annotations

from typing import Any

from agents.rules import (
    AnalysisResult,
    ComplexityResult,
    analyze_query_rules,
    classify_complexity,
)
from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer

logger = get_logger("agents.nodes.assess_complexity")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def assess_complexity(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """Execute complexity assessment node (F3).

    Evaluates query and prior analysis to classify complexity tier, determine allowed
    retrieval strategies, and enforce sub-question count ceilings.

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

    # Reconstruct or derive AnalysisResult for rule evaluation
    if "needs_sql" in existing_meta and "needs_graph" in existing_meta:
        analysis = AnalysisResult(
            intent=str(_get_field(state, "intent", "factual_query") or "factual_query"),
            entities=list(existing_meta.get("entities", [])),
            time_range=existing_meta.get("time_range_raw"),
            needs_sql=bool(existing_meta.get("needs_sql", False)),
            needs_graph=bool(existing_meta.get("needs_graph", False)),
            needs_documents=bool(existing_meta.get("needs_documents", False)),
            needs_relationships=bool(existing_meta.get("needs_relationships", False)),
            needs_aggregation=bool(existing_meta.get("needs_aggregation", False)),
        )
    else:
        analysis = analyze_query_rules(question)

    # Deterministic complexity classification floor (Claude.md §7.2, §7.3)
    result: ComplexityResult = classify_complexity(question, analysis)

    # Telemetry wrapping with zero-crash guarantee
    tracer = get_tracer()
    try:
        with tracer.node(session_id=session_id, node_name="assess_complexity") as ctx:
            if ctx and hasattr(ctx, "payload"):
                ctx.payload.update(
                    {
                        "complexity": result.complexity,
                        "rule_applied": result.rule_applied,
                        "max_subquestions": result.max_subquestions,
                        "allowed_strategies": result.allowed_strategies,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telemetry error in assess_complexity (session=%s): %s",
            session_id,
            exc,
        )

    # Return partial state dictionary
    return {
        "current_node": "assess_complexity",
        "complexity": result.complexity,
        "metadata": {
            **existing_meta,
            "complexity_rule": result.rule_applied,
            "max_subquestions": result.max_subquestions,
            "allowed_strategies": result.allowed_strategies,
            "complexity_rationale": result.rationale,
        },
    }


# LangGraph node alias
assess_complexity_node = assess_complexity
