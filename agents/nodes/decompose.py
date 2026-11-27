"""Sub-question decomposition node for LangGraph research workflow (P9-3, F4, Claude.md §3.1, §7.3).

Primary Responsibilities:
- Decompose complex questions into <= MAX_SUBQUESTIONS (default 4) focused sub-questions.
- Enforce strict complexity-driven workflow shape:
    - simple: exactly 1 sub-question, strictly 'vector' retrieval only.
    - moderate: 1–2 sub-questions.
    - complex: <= 4 sub-questions; canonical 4-way decomposition (graph, sql, graph, hybrid).
- Enforce deterministic routing floors via enforce_routing_floor().
- Wrap execution in tracer.node(...) without allowing telemetry to crash the workflow.
- Return partial state dictionary updating: sub_questions and metadata.
"""

from __future__ import annotations

from typing import Any

from agents.rules import (
    MAX_SUBQUESTIONS,
    AnalysisResult,
    ComplexityLevel,
    SubQuestion,
    analyze_query_rules,
    classify_complexity,
    decompose_query_rules,
    enforce_routing_floor,
)
from agents.state import ResearchState
from backend.app.core.logging import get_logger
from backend.app.core.observability import get_tracer

logger = get_logger("agents.nodes.decompose")


def _get_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState instance or a dict."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def decompose(state: ResearchState | dict[str, Any]) -> dict[str, Any]:
    """Execute sub-question decomposition node (F4).

    Splits query into focused, strategy-assigned sub-questions respecting complexity
    ceilings and deterministic routing floors.

    Args:
        state: Shared ResearchState or state dictionary.

    Returns:
        Partial state update dict for LangGraph StateGraph.
    """
    question = str(_get_field(state, "question", "") or "").strip()
    session_id = str(
        _get_field(state, "session_id", "default-session") or "default-session"
    )
    raw_complexity = _get_field(state, "complexity")
    intent = str(_get_field(state, "intent", "factual_query") or "factual_query")
    entity = _get_field(state, "entity")
    existing_meta = dict(_get_field(state, "metadata", {}) or {})

    # 1. Reconstruct or derive AnalysisResult
    if "needs_sql" in existing_meta and "needs_graph" in existing_meta:
        analysis = AnalysisResult(
            intent=intent,
            entities=list(existing_meta.get("entities", []))
            or ([entity] if entity else []),
            time_range=existing_meta.get("time_range_raw"),
            needs_sql=bool(existing_meta.get("needs_sql", False)),
            needs_graph=bool(existing_meta.get("needs_graph", False)),
            needs_documents=bool(existing_meta.get("needs_documents", False)),
            needs_relationships=bool(existing_meta.get("needs_relationships", False)),
            needs_aggregation=bool(existing_meta.get("needs_aggregation", False)),
        )
    else:
        analysis = analyze_query_rules(question)

    # 2. Determine or validate complexity tier
    if raw_complexity in ("simple", "moderate", "complex"):
        complexity: ComplexityLevel = raw_complexity
    else:
        complexity = classify_complexity(question, analysis).complexity

    # 3. Deterministic rule-based decomposition (Claude.md §7.2, §7.3)
    raw_sub_questions: list[SubQuestion] = decompose_query_rules(question, analysis)

    # 4. Enforce complexity constraints and routing floors
    bounded_sub_questions: list[SubQuestion] = []
    if complexity == "simple":
        target = analysis.entities[0] if analysis.entities else (entity or None)
        first_q = (
            raw_sub_questions[0].question
            if raw_sub_questions
            else (question or "Factual lookup")
        )
        bounded_sub_questions = [
            SubQuestion(
                id="sq1",
                question=first_q,
                strategy="vector",
                target_entity=target,
                rule_applied="RULE_FLOOR_SIMPLE_ONLY_VECTOR",
                rationale="Simple complexity inquiries are restricted to exactly 1 vector sub-question.",
            )
        ]
    elif complexity == "moderate":
        # At most 2 sub-questions for moderate inquiries
        max_moderate = min(2, len(raw_sub_questions)) if raw_sub_questions else 1
        for idx in range(max_moderate):
            sq = raw_sub_questions[idx]
            floored = enforce_routing_floor(sq, overall_complexity=complexity)
            bounded_sub_questions.append(
                SubQuestion(
                    id=f"sq{idx + 1}",
                    question=floored.question,
                    strategy=floored.strategy,
                    target_entity=floored.target_entity,
                    rule_applied=floored.rule_applied,
                    rationale=floored.rationale,
                    metadata=floored.metadata,
                )
            )
    else:
        # Complex: bounded strictly by MAX_SUBQUESTIONS (4)
        for idx, sq in enumerate(raw_sub_questions[:MAX_SUBQUESTIONS]):
            floored = enforce_routing_floor(sq, overall_complexity=complexity)
            bounded_sub_questions.append(
                SubQuestion(
                    id=f"sq{idx + 1}",
                    question=floored.question,
                    strategy=floored.strategy,
                    target_entity=floored.target_entity,
                    rule_applied=floored.rule_applied,
                    rationale=floored.rationale,
                    metadata=floored.metadata,
                )
            )

    # Hard ceiling defense
    final_sub_questions = bounded_sub_questions[:MAX_SUBQUESTIONS]

    # 5. Telemetry wrapping with zero-crash guarantee
    tracer = get_tracer()
    try:
        with tracer.node(session_id=session_id, node_name="decompose") as ctx:
            if ctx and hasattr(ctx, "payload"):
                ctx.payload.update(
                    {
                        "complexity": complexity,
                        "sub_questions_count": len(final_sub_questions),
                        "strategies": [sq.strategy for sq in final_sub_questions],
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telemetry error in decompose (session=%s): %s",
            session_id,
            exc,
        )

    # 6. Return partial state dictionary
    return {
        "current_node": "decompose",
        "sub_questions": [sq.model_dump() for sq in final_sub_questions],
        "metadata": {
            **existing_meta,
            "sub_questions_count": len(final_sub_questions),
            "decomposition_rule": (
                final_sub_questions[0].rule_applied
                if final_sub_questions
                else "RULE_DECOMP_DEFAULT"
            ),
        },
    }


# LangGraph node alias
decompose_node = decompose
