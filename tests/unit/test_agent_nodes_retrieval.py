"""Unit tests for retrieval routing and execution nodes (P9-4, F5, F6, F7, F8, Claude.md §3.1, §5, §7.3).

Validates:
- F5: Assigning vector, sql, graph, or hybrid strategies per sub-question
- F6: Hybrid document retrieval integration (semantic + BM25 + RRF + rerank)
- F7: Governed SQL retrieval restricted to read-only allowlist
- F8: Graph retrieval via typed traversals exposing Cypher
- Simple complexity invariant: strategies_used contains only 'vector'
- Bounded fault tolerance: store failure records an error on the sub-question without crashing workflow
- Telemetry integration via tracer.node() and tracer.record_query() with failure resilience
- Dual support for ResearchState instances and raw dicts
- Sequential pipeline execution: analyze_query -> assess_complexity -> decompose -> route_retrieval -> execute_retrieval
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agents.nodes.analyze_query import analyze_query
from agents.nodes.assess_complexity import assess_complexity
from agents.nodes.decompose import decompose
from agents.nodes.execute_retrieval import execute_retrieval, execute_retrieval_node
from agents.nodes.route_retrieval import route_retrieval, route_retrieval_node
from agents.rules import CANONICAL_QUESTION_TEXT
from agents.state import ResearchState
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.core.observability import get_tracer
from backend.app.services.seed import seed_database
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store
from rag.retriever import HybridRetriever
from rag.vector_store import InMemoryVectorStore, get_vector_store


@pytest.fixture(autouse=True)
def setup_test_stores() -> Any:
    """Initialize in-memory relational, graph, and vector stores with sample data."""
    # 1. SQL in-memory SQLite
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        seed_database(session)

    # 2. Graph in-memory store
    store = get_graph_store()
    if isinstance(store, InMemoryGraphStore):
        sample_dir = Path(__file__).resolve().parents[2] / "sample_data"
        seed_graph_from_domain(store, sample_data_dir=sample_dir)

    # 3. Vector in-memory store populated with sample document chunks
    v_store = get_vector_store()
    if isinstance(v_store, InMemoryVectorStore) and v_store.count() == 0:
        sample_chunks = [
            {
                "id": "chunk-adr-042",
                "document_id": "doc-adr-042",
                "text": "ADR-042: PgBouncer connection pooling introduced to mitigate connection spikes during Payments API failovers.",
                "metadata": {
                    "filename": "adr-042.md",
                    "section": "Decision",
                    "chunk_index": 0,
                    "entity": "Payments API",
                },
            },
            {
                "id": "chunk-postmortem-payments",
                "document_id": "doc-pm-payments",
                "text": "Postmortem 2026-Q2: Payments API connection exhaustion caused SEV1 outage. Mitigation requires dedicated PgBouncer pool.",
                "metadata": {
                    "filename": "postmortem-payments.md",
                    "section": "Root Cause",
                    "chunk_index": 0,
                    "entity": "Payments API",
                },
            },
            {
                "id": "chunk-retention-policy",
                "document_id": "doc-retention",
                "text": "Corporate Data Retention Policy: Customer audit logs are preserved for 365 days under cold storage retention.",
                "metadata": {
                    "filename": "retention-policy.md",
                    "section": "Policy",
                    "chunk_index": 0,
                },
            },
        ]
        HybridRetriever(vector_store=v_store).index_chunks(sample_chunks)

    yield


def test_route_retrieval_canonical_question() -> None:
    """F5: Verify route_retrieval assigns strategies and populates strategies_used."""
    state = ResearchState(
        session_id="test-route-canonical",
        question=CANONICAL_QUESTION_TEXT,
    )
    for k, v in analyze_query(state).items():
        state[k] = v
    for k, v in assess_complexity(state).items():
        state[k] = v
    for k, v in decompose(state).items():
        state[k] = v

    out = route_retrieval(state)

    assert isinstance(out, dict)
    assert out["current_node"] == "route_retrieval"
    sub_questions = out["sub_questions"]
    assert len(sub_questions) == 4

    strategies = [sq["strategy"] for sq in sub_questions]
    assert strategies == ["graph", "sql", "graph", "hybrid"]

    strategies_used = out["strategies_used"]
    assert set(strategies_used) == {"graph", "sql", "hybrid"}
    assert "strategies_used" in out["metadata"]


def test_route_retrieval_simple_query_enforces_vector_only() -> None:
    """Claude.md §7.3: For simple complexity, strategies_used contains only 'vector'."""
    state = ResearchState(
        session_id="test-route-simple",
        question="What is our corporate data retention policy for customer logs?",
        complexity="simple",
        sub_questions=[
            {
                "id": "sq1",
                "question": "What is our corporate data retention policy for customer logs?",
                "strategy": "sql",  # Non-vector strategy to test routing floor override
            }
        ],
    )

    out = route_retrieval(state)

    assert out["current_node"] == "route_retrieval"
    assert out["sub_questions"][0]["strategy"] == "vector"
    assert out["strategies_used"] == ["vector"]


def test_route_retrieval_raw_dict_and_alias() -> None:
    """Verify route_retrieval accepts raw dict and alias route_retrieval_node works."""
    raw_dict: dict[str, Any] = {
        "session_id": "test-route-dict",
        "complexity": "moderate",
        "sub_questions": [
            {
                "id": "sq1",
                "question": "Which team owns the Auth Service?",
                "strategy": "vector",
            }
        ],
    }

    out = route_retrieval_node(raw_dict)
    assert out["current_node"] == "route_retrieval"
    assert out["sub_questions"][0]["strategy"] == "graph"
    assert "graph" in out["strategies_used"]


def test_execute_retrieval_multi_store_evidence_collection() -> None:
    """F6, F7, F8: Verify execute_retrieval pulls evidence across graph, sql, and hybrid stores."""
    state = ResearchState(
        session_id="test-exec-multi",
        question=CANONICAL_QUESTION_TEXT,
        entity="Payments API",
        time_range={
            "start_date": "2026-04-01T00:00:00Z",
            "end_date": "2026-06-30T23:59:59Z",
        },
        sub_questions=[
            {
                "id": "sq1",
                "question": "Which customers were impacted by incidents on the Payments API?",
                "strategy": "graph",
                "target_entity": "Payments API",
            },
            {
                "id": "sq2",
                "question": "What incidents occurred on the Payments API during last quarter?",
                "strategy": "sql",
                "target_entity": "Payments API",
            },
            {
                "id": "sq3",
                "question": "Which teams own the services related to Payments API?",
                "strategy": "graph",
                "target_entity": "Payments API",
            },
            {
                "id": "sq4",
                "question": "What decisions and postmortems were documented to prevent recurrence?",
                "strategy": "hybrid",
                "target_entity": "Payments API",
            },
        ],
    )

    out = execute_retrieval(state)

    assert isinstance(out, dict)
    assert out["current_node"] == "execute_retrieval"
    evidence_list = out["evidence"]
    assert len(evidence_list) >= 4, (
        f"Expected at least 4 evidence items, got {len(evidence_list)}"
    )

    source_types = {
        e.source_type if hasattr(e, "source_type") else e["source_type"]
        for e in evidence_list
    }
    assert "graph" in source_types
    assert "sql" in source_types
    assert "document" in source_types

    # Verify locators
    for e in evidence_list:
        loc = e.locator if hasattr(e, "locator") else e["locator"]
        st = e.source_type if hasattr(e, "source_type") else e["source_type"]
        if st == "graph":
            assert loc.startswith(("graph:", "("))
        elif st == "sql":
            assert loc.startswith("sql:")
        elif st == "document":
            assert loc.startswith(("documents/", "doc:"))


def test_execute_retrieval_simple_vector_only() -> None:
    """Claude.md §7.3: Simple retrieval queries vector/document store only."""
    state = ResearchState(
        session_id="test-exec-simple",
        question="What is our corporate data retention policy for customer logs?",
        complexity="simple",
        sub_questions=[
            {
                "id": "sq1",
                "question": "What is our corporate data retention policy for customer logs?",
                "strategy": "vector",
            }
        ],
    )

    out = execute_retrieval_node(state)
    assert out["current_node"] == "execute_retrieval"
    evidence_list = out["evidence"]
    assert len(evidence_list) >= 1

    for e in evidence_list:
        st = e.source_type if hasattr(e, "source_type") else e["source_type"]
        assert st == "document"


def test_execute_retrieval_store_failure_resilience() -> None:
    """Claude.md §7.3: Store failure records an error on the sub-question; it must never crash the workflow."""
    state = ResearchState(
        session_id="test-exec-failure",
        question="What incidents occurred on Payments API?",
        sub_questions=[
            {
                "id": "sq1",
                "question": "What incidents occurred on Payments API?",
                "strategy": "sql",
            },
            {
                "id": "sq2",
                "question": "What architectural decisions apply to Payments API?",
                "strategy": "hybrid",
            },
        ],
    )

    # Force SQL execution to fail
    with patch(
        "agents.nodes.execute_retrieval.execute_governed_sql",
        side_effect=RuntimeError("Database connection dropped"),
    ):
        out = execute_retrieval(state)

        assert out["current_node"] == "execute_retrieval"
        # Errors list must record the failure
        assert len(out["errors"]) >= 1
        assert any("Database connection dropped" in err for err in out["errors"])

        # Hybrid retrieval must still succeed
        assert len(out["evidence"]) >= 1
        assert any(
            (e.source_type if hasattr(e, "source_type") else e["source_type"])
            == "document"
            for e in out["evidence"]
        )


def test_route_and_execute_telemetry_resilience() -> None:
    """Claude.md §7.3: Telemetry failures must never crash route or execute nodes."""
    state = ResearchState(
        session_id="test-retrieval-telemetry",
        question="What is our corporate data retention policy?",
        complexity="simple",
        sub_questions=[
            {
                "id": "sq1",
                "question": "What is our retention policy?",
                "strategy": "vector",
            }
        ],
    )

    with (
        patch.object(
            get_tracer(), "record_event", side_effect=RuntimeError("Tracer failed")
        ),
        patch.object(
            get_tracer(),
            "record_query",
            side_effect=RuntimeError("Tracer query failed"),
        ),
    ):
        out_route = route_retrieval(state)
        assert out_route["current_node"] == "route_retrieval"

        for k, v in out_route.items():
            state[k] = v

        out_exec = execute_retrieval(state)
        assert out_exec["current_node"] == "execute_retrieval"
        assert len(out_exec["evidence"]) >= 1


def test_five_node_sequential_chain_pipeline() -> None:
    """Verify sequential execution of the first 5 LangGraph workflow nodes."""
    state = ResearchState(
        session_id="test-5node-pipeline",
        question=CANONICAL_QUESTION_TEXT,
    )

    # 1. analyze_query
    for k, v in analyze_query(state).items():
        state[k] = v
    assert state.current_node == "analyze_query"

    # 2. assess_complexity
    for k, v in assess_complexity(state).items():
        state[k] = v
    assert state.current_node == "assess_complexity"

    # 3. decompose
    for k, v in decompose(state).items():
        state[k] = v
    assert state.current_node == "decompose"
    assert len(state.sub_questions) == 4

    # 4. route_retrieval
    for k, v in route_retrieval(state).items():
        state[k] = v
    assert state.current_node == "route_retrieval"
    assert set(state.strategies_used) == {"graph", "sql", "hybrid"}

    # 5. execute_retrieval
    for k, v in execute_retrieval(state).items():
        state[k] = v
    assert state.current_node == "execute_retrieval"
    assert len(state.evidence) >= 4
