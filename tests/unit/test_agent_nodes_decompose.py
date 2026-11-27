"""Unit tests for sub-question decomposition node (P9-3, F4, Claude.md §3.1, §7.3).

Validates:
- F4: Decomposes complex queries into <= MAX_SUBQUESTIONS (default 4)
- Canonical question produces 4 sub-questions in exact order: graph, sql, graph, hybrid
- Simple complexity query produces exactly 1 sub-question with strategy 'vector'
- Moderate complexity query produces <= 2 sub-questions
- Sub-questions carry sequential IDs sq1..sq4 and valid strategy assignments
- Telemetry recording via tracer.node() with zero-crash guarantee on telemetry failure
- Dual support for ResearchState instances and raw dicts
- Sequential pipeline execution: analyze_query -> assess_complexity -> decompose
"""

from typing import Any
from unittest.mock import patch

from agents.nodes.analyze_query import analyze_query
from agents.nodes.assess_complexity import assess_complexity
from agents.nodes.decompose import decompose, decompose_node
from agents.rules import CANONICAL_QUESTION_TEXT, MAX_SUBQUESTIONS
from agents.state import ResearchState
from backend.app.core.observability import get_tracer


def test_decompose_canonical_question_four_subquestions() -> None:
    """F4, Claude.md §7.3: Canonical question produces 4 sub-questions in exact strategy order."""
    state = ResearchState(
        session_id="test-canonical-decomp",
        question=CANONICAL_QUESTION_TEXT,
    )
    # Run prior nodes
    out1 = analyze_query(state)
    for k, v in out1.items():
        state[k] = v

    out2 = assess_complexity(state)
    for k, v in out2.items():
        state[k] = v

    # Run decompose node
    out3 = decompose(state)

    assert isinstance(out3, dict)
    assert out3["current_node"] == "decompose"
    sub_questions = out3["sub_questions"]
    assert len(sub_questions) == 4, (
        f"Expected 4 sub-questions, got {len(sub_questions)}"
    )

    # Check sequential IDs
    ids = [sq["id"] for sq in sub_questions]
    assert ids == ["sq1", "sq2", "sq3", "sq4"]

    # Check exact strategies (Claude.md §415: graph, sql, graph, hybrid)
    strategies = [sq["strategy"] for sq in sub_questions]
    assert strategies == ["graph", "sql", "graph", "hybrid"]

    # Verify facets
    assert "customers" in sub_questions[0]["question"].lower()
    assert sub_questions[0]["target_entity"] == "Payments API"

    assert "incidents" in sub_questions[1]["question"].lower()
    assert sub_questions[1]["strategy"] == "sql"

    assert "teams" in sub_questions[2]["question"].lower()
    assert sub_questions[2]["strategy"] == "graph"

    assert (
        "decisions" in sub_questions[3]["question"].lower()
        or "postmortem" in sub_questions[3]["question"].lower()
    )
    assert sub_questions[3]["strategy"] == "hybrid"


def test_decompose_simple_query_single_vector_subquestion() -> None:
    """F4, Claude.md §7.3: Simple query produces exactly 1 sub-question with strategy 'vector'."""
    question = "What is our corporate data retention policy for customer logs?"
    state = ResearchState(session_id="test-simple-decomp", question=question)

    out1 = analyze_query(state)
    for k, v in out1.items():
        state[k] = v

    out2 = assess_complexity(state)
    for k, v in out2.items():
        state[k] = v

    assert state.complexity == "simple"

    out3 = decompose(state)
    sub_questions = out3["sub_questions"]

    assert len(sub_questions) == 1
    assert sub_questions[0]["id"] == "sq1"
    assert sub_questions[0]["strategy"] == "vector"
    assert "sql" != sub_questions[0]["strategy"]
    assert "graph" != sub_questions[0]["strategy"]


def test_decompose_moderate_query_bounded_subquestions() -> None:
    """F4: Moderate query produces at most 2 sub-questions."""
    queries = [
        "How many SEV1 incidents occurred in the Payments API?",
        "Which team owns the Auth Service and Payments API?",
    ]

    for q in queries:
        state = ResearchState(session_id="test-moderate-decomp", question=q)
        for k, v in analyze_query(state).items():
            state[k] = v
        for k, v in assess_complexity(state).items():
            state[k] = v

        assert state.complexity == "moderate"

        out = decompose_node(state)
        sub_questions = out["sub_questions"]
        assert 1 <= len(sub_questions) <= 2
        assert sub_questions[0]["id"] == "sq1"


def test_decompose_hard_ceiling_never_exceeds_max_subquestions() -> None:
    """Claude.md §7.3: MAX_SUBQUESTIONS (4) is a non-negotiable hard ceiling."""
    complex_multi_facet = (
        "Show incidents, impacted customers, team ownership, ADR decisions, SLAs, "
        "and error rates for Core Banking across Q1, Q2, and Q3."
    )
    state = ResearchState(session_id="test-ceiling", question=complex_multi_facet)

    for k, v in analyze_query(state).items():
        state[k] = v
    for k, v in assess_complexity(state).items():
        state[k] = v

    out = decompose(state)
    assert len(out["sub_questions"]) <= MAX_SUBQUESTIONS


def test_decompose_dict_input_and_alias() -> None:
    """Verify decompose accepts raw dict input and decompose_node alias works identically."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-decomp",
        "question": "What is our disaster recovery runbook?",
        "complexity": "simple",
        "intent": "factual_query",
        "metadata": {"needs_documents": True},
    }

    out = decompose_node(dict_state)

    assert out["current_node"] == "decompose"
    assert len(out["sub_questions"]) == 1
    assert out["sub_questions"][0]["strategy"] == "vector"


def test_decompose_telemetry_resilience_when_tracer_raises() -> None:
    """Claude.md §7.3: Telemetry failures must never crash decompose node."""
    state = ResearchState(
        session_id="test-telemetry-decomp",
        question="What is our SLA policy?",
        complexity="simple",
    )

    with patch.object(
        get_tracer(), "record_event", side_effect=RuntimeError("Tracer failed")
    ):
        out = decompose(state)
        assert out["current_node"] == "decompose"
        assert len(out["sub_questions"]) >= 1


def test_decompose_empty_query_fallback() -> None:
    """Verify empty query produces a safe fallback sub-question."""
    state = ResearchState(session_id="test-empty-decomp", question="")

    out = decompose(state)
    assert out["current_node"] == "decompose"
    assert len(out["sub_questions"]) == 1
    assert out["sub_questions"][0]["strategy"] == "vector"


def test_three_node_sequential_chain_pipeline() -> None:
    """Verify end-to-end execution of the first 3 LangGraph nodes."""
    state = ResearchState(
        session_id="test-pipeline",
        question=CANONICAL_QUESTION_TEXT,
    )

    # Node 1: analyze_query
    u1 = analyze_query(state)
    for k, v in u1.items():
        state[k] = v
    assert state.entity == "Payments API"
    assert state.current_node == "analyze_query"

    # Node 2: assess_complexity
    u2 = assess_complexity(state)
    for k, v in u2.items():
        state[k] = v
    assert state.complexity == "complex"
    assert state.current_node == "assess_complexity"

    # Node 3: decompose
    u3 = decompose(state)
    for k, v in u3.items():
        state[k] = v
    assert state.current_node == "decompose"
    assert len(state.sub_questions) == 4
    assert [sq["strategy"] for sq in state.sub_questions] == [
        "graph",
        "sql",
        "graph",
        "hybrid",
    ]
