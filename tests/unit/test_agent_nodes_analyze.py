"""Unit tests for query analysis and complexity assessment nodes (P9-2, F2, F3, Claude.md §3.1, §7.3).

Validates:
- F2: Intent, entity, time range, and store need extraction in `agents/nodes/analyze_query.py`
- F3: Complexity classification (simple / moderate / complex) in `agents/nodes/assess_complexity.py`
- Fiscal calendar resolution via organizational memory (e.g. 'last quarter' -> 2026-Q2)
- Deterministic rules-plus-LLM pattern establishing routing floors
- Strict complexity shape: simple -> 1 sub-question, vector only, no SQL/Cypher
- Telemetry integration via tracer.node() with zero-crash guarantee on telemetry failure
- Dual support for ResearchState instances and raw dicts
"""

from typing import Any
from unittest.mock import patch

from agents.nodes.analyze_query import analyze_query, analyze_query_node
from agents.nodes.assess_complexity import assess_complexity, assess_complexity_node
from agents.rules import CANONICAL_QUESTION_TEXT
from agents.state import ResearchState
from backend.app.core.observability import get_tracer


def test_analyze_query_canonical_question() -> None:
    """F2: Verify analyze_query extracts entity, intent, modalities, and fiscal date bounds."""
    state = ResearchState(
        session_id="test-session-canonical",
        question=CANONICAL_QUESTION_TEXT,
    )

    update = analyze_query(state)

    assert isinstance(update, dict)
    assert update["current_node"] == "analyze_query"
    assert update["entity"] == "Payments API"
    assert update["intent"] == "cross_domain_research"

    # Fiscal calendar mapping: 'last quarter' -> 2026-Q2
    time_range = update["time_range"]
    assert isinstance(time_range, dict)
    assert time_range.get("start_date") == "2026-04-01T00:00:00Z"
    assert time_range.get("end_date") == "2026-06-30T23:59:59Z"
    assert "2026-Q2" in time_range.get("quarter", "")
    assert "Fiscal Q2" in time_range.get("quarter_name", "")

    # Store modality flags in metadata
    meta = update["metadata"]
    assert meta["needs_sql"] is True
    assert meta["needs_graph"] is True
    assert meta["needs_documents"] is True
    assert meta["needs_relationships"] is True
    assert "Payments API" in meta["entities"]


def test_analyze_query_simple_factual_question() -> None:
    """F2: Verify simple factual lookups have no fiscal quarter and document-only modalities."""
    question = "What is the token TTL expiration for analyst sessions under our corporate data retention policy?"
    state = ResearchState(session_id="test-session-simple", question=question)

    update = analyze_query(state)

    assert update["current_node"] == "analyze_query"
    assert update["intent"] == "factual_query"
    assert update["entity"] is None
    # No temporal filter mentioned in query
    assert update["time_range"] == {}
    assert update["metadata"]["needs_sql"] is False
    assert update["metadata"]["needs_graph"] is False
    assert update["metadata"]["needs_documents"] is True


def test_analyze_query_dict_input_and_alias() -> None:
    """Verify analyze_query accepts raw dict and analyze_query_node alias works identically."""
    dict_state: dict[str, Any] = {
        "session_id": "test-session-dict",
        "question": "Which team owns the Auth Service and what are its dependencies?",
    }

    update = analyze_query_node(dict_state)

    assert update["current_node"] == "analyze_query"
    assert update["entity"] == "Auth Service"
    assert update["metadata"]["needs_graph"] is True
    assert update["metadata"]["needs_relationships"] is True


def test_analyze_query_fiscal_quarters_resolution() -> None:
    """F2: Verify mapping of relative and explicit quarter references against organizational memory."""
    test_cases = [
        (
            "What incidents occurred last quarter in Payments API?",
            "2026-04-01T00:00:00Z",
            "2026-06-30T23:59:59Z",
            "2026-Q2",
        ),
        (
            "Show me outages in 2026-Q1 for Core Banking",
            "2026-01-01T00:00:00Z",
            "2026-03-31T23:59:59Z",
            "2026-Q1",
        ),
        (
            "Report on this quarter performance",
            "2026-07-01T00:00:00Z",
            "2026-09-30T23:59:59Z",
            "2026-Q3",
        ),
    ]

    for question, expected_start, expected_end, expected_qtr in test_cases:
        state = ResearchState(session_id="test-fiscal", question=question)
        update = analyze_query(state)
        tr = update["time_range"]
        assert tr.get("start_date") == expected_start, (
            f"Failed start_date for: {question}"
        )
        assert tr.get("end_date") == expected_end, f"Failed end_date for: {question}"
        assert expected_qtr in tr.get("quarter", ""), (
            f"Failed quarter identifier for: {question}"
        )


def test_assess_complexity_canonical_question() -> None:
    """F3: Verify canonical 4-way cross-domain question classifies as 'complex' with max 4 sub-questions."""
    state = ResearchState(
        session_id="test-complexity-canonical",
        question=CANONICAL_QUESTION_TEXT,
    )
    # First analyze query
    analysis_update = analyze_query(state)
    for k, v in analysis_update.items():
        state[k] = v

    complexity_update = assess_complexity(state)

    assert complexity_update["current_node"] == "assess_complexity"
    assert complexity_update["complexity"] == "complex"
    meta = complexity_update["metadata"]
    assert meta["complexity_rule"] == "RULE_CANONICAL_QUERY"
    assert meta["max_subquestions"] == 4
    assert set(meta["allowed_strategies"]) == {"graph", "sql", "hybrid", "vector"}
    assert "cross-domain" in meta["complexity_rationale"].lower()


def test_assess_complexity_simple_query_invariants() -> None:
    """F3, Claude.md §7.3: Verify simple query enforces 1 sub-question and strictly vector only."""
    questions = [
        "What is our corporate data retention policy for customer logs?",
        "What does ADR-042 recommend for connection pooling?",
    ]

    for q in questions:
        state = ResearchState(session_id="test-simple-shape", question=q)
        analysis_update = analyze_query(state)
        for k, v in analysis_update.items():
            state[k] = v

        complexity_update = assess_complexity(state)

        assert complexity_update["complexity"] == "simple"
        meta = complexity_update["metadata"]
        assert meta["max_subquestions"] == 1
        assert meta["allowed_strategies"] == ["vector"]
        assert "sql" not in meta["allowed_strategies"]
        assert "graph" not in meta["allowed_strategies"]
        assert meta["complexity_rule"].startswith("RULE_SIMPLE")


def test_assess_complexity_moderate_query() -> None:
    """F3: Verify single-domain metrics or single-hop relationships classify as 'moderate'."""
    queries = [
        ("How many SEV1 incidents occurred in the Payments API?", 2),
        ("Which team owns the Auth Service?", 2),
        ("List all customers with active Enterprise tier status.", 2),
    ]

    for q, max_sq in queries:
        state = ResearchState(session_id="test-moderate", question=q)
        analysis_update = analyze_query(state)
        for k, v in analysis_update.items():
            state[k] = v

        complexity_update = assess_complexity_node(state)

        assert complexity_update["complexity"] == "moderate"
        meta = complexity_update["metadata"]
        assert meta["max_subquestions"] == max_sq
        assert meta["complexity_rule"] in {
            "RULE_SINGLE_DOMAIN_METRIC",
            "RULE_SINGLE_DOMAIN_RELATIONSHIP",
        }


def test_chain_analyze_and_assess_nodes_flow() -> None:
    """Verify standard LangGraph node sequential chain execution."""
    state = ResearchState(
        session_id="test-chain",
        question="Which customers were affected by Payments API outages?",
    )

    # 1. Node analyze_query
    out1 = analyze_query(state)
    for k, v in out1.items():
        state[k] = v

    assert state.entity == "Payments API"
    assert state.current_node == "analyze_query"

    # 2. Node assess_complexity
    out2 = assess_complexity(state)
    for k, v in out2.items():
        state[k] = v

    assert state.current_node == "assess_complexity"
    assert state.complexity in {"moderate", "complex"}
    assert state.metadata["max_subquestions"] in {2, 4}


def test_telemetry_resilience_when_tracer_raises() -> None:
    """Claude.md §7.3: Node execution must never crash if telemetry or tracing fails."""
    state = ResearchState(
        session_id="test-telemetry-resilience",
        question="What is our corporate data retention policy for customer logs?",
    )

    with patch.object(
        get_tracer(),
        "record_event",
        side_effect=RuntimeError("Telemetry store unavailable"),
    ):
        # Both nodes must execute and return valid partial dicts without raising
        out_analysis = analyze_query(state)
        assert out_analysis["current_node"] == "analyze_query"

        for k, v in out_analysis.items():
            state[k] = v

        out_complexity = assess_complexity(state)
        assert out_complexity["current_node"] == "assess_complexity"
        assert out_complexity["complexity"] == "simple"


def test_empty_and_unknown_query_graceful_handling() -> None:
    """Verify graceful fallback for empty, whitespace, and unrecognized queries."""
    state = ResearchState(session_id="test-empty", question="   ")

    out_analysis = analyze_query(state)
    assert out_analysis["entity"] is None
    assert out_analysis["time_range"] == {}

    for k, v in out_analysis.items():
        state[k] = v

    out_complexity = assess_complexity(state)
    assert out_complexity["complexity"] == "simple"
    assert out_complexity["metadata"]["max_subquestions"] == 1
