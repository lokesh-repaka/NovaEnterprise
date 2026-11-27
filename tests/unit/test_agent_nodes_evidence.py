"""Unit tests for evidence collection and missing-evidence evaluation nodes (P9-5, F9, Claude.md §3.1, §5, §7.3).

Validates:
- Node 6: collect_evidence:
  - Normalizes raw dicts and Evidence models into canonical Evidence schema
  - Deduplicates evidence items by (source_type, locator), preserving the highest score
  - Preserves citation locators across documents, SQL, and graph stores
  - Telemetry resilience via tracer.node()
  - Support for both ResearchState models and raw dicts
- Node 7: check_missing_evidence:
  - Evaluates sub-question coverage against collected evidence
  - F9: When sub-questions lack evidence and corrective_rounds < max_rounds, triggers retry (needs_retry=True)
  - test_corrective_retrieval_triggers_for_unanswerable_part: confirms unbacked facet triggers retry
  - Bounded loop: When corrective_rounds >= MAX_CORRECTIVE_ROUNDS (1), terminates loop (needs_retry=False)
  - When all sub-questions are backed by evidence, terminates cleanly (needs_retry=False, missing_facets=[])
  - Telemetry resilience via tracer.node()
- End-to-end sequential chaining:
  analyze_query -> assess_complexity -> decompose -> route_retrieval -> execute_retrieval -> collect_evidence -> check_missing_evidence
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agents.nodes.analyze_query import analyze_query
from agents.nodes.assess_complexity import assess_complexity
from agents.nodes.check_missing_evidence import (
    check_missing_evidence,
    check_missing_evidence_node,
)
from agents.nodes.collect_evidence import (
    collect_evidence,
    collect_evidence_node,
)
from agents.nodes.decompose import decompose
from agents.nodes.execute_retrieval import execute_retrieval
from agents.nodes.route_retrieval import route_retrieval
from agents.rules import CANONICAL_QUESTION_TEXT
from agents.state import ResearchState
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.schemas.common import Evidence
from backend.app.services.seed import seed_database
from rag.evidence import (
    create_document_evidence,
    create_evidence,
    create_graph_evidence,
    create_sql_evidence,
)
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
                    "source": "documents/adr-042-pgbouncer.md",
                    "chunk_index": 0,
                },
            },
            {
                "id": "chunk-q2-review",
                "document_id": "doc-q2-review",
                "text": "Executive Q2 incident post-mortem: Payments API experienced cascading timeouts due to connection exhaustion.",
                "metadata": {
                    "source": "documents/q2-incident-post-mortem.md",
                    "chunk_index": 1,
                },
            },
        ]
        v_store.add_documents(sample_chunks)
        HybridRetriever(vector_store=v_store).index_chunks(sample_chunks)

    yield


# =============================================================================
# Node 6: collect_evidence Tests
# =============================================================================


def test_collect_evidence_normalizes_and_deduplicates() -> None:
    """Test collect_evidence merges raw items, normalizes dicts, and deduplicates highest score."""
    raw_doc_dict = {
        "id": "evi_custom_1",
        "sub_question_id": "sq1",
        "source_type": "document",
        "locator": "documents/adr-042-pgbouncer.md#chunk-0",
        "content": "PgBouncer connection pooling documentation.",
        "score": 0.75,
        "metadata": {"source": "documents/adr-042-pgbouncer.md"},
    }
    higher_score_doc = create_evidence(
        sub_question_id="sq1",
        source_type="document",
        locator="documents/adr-042-pgbouncer.md#chunk-0",
        content="PgBouncer connection pooling documentation with higher confidence.",
        score=0.95,
        metadata={"source": "documents/adr-042-pgbouncer.md"},
    )
    sql_item = create_sql_evidence(
        sub_question_id="sq2",
        table="incidents",
        row_id="inc-2021",
        content="Incident inc-2021: Payments API connection timeout.",
        score=0.88,
    )

    state = ResearchState(
        session_id="test-session-collect",
        question="What happened to Payments API?",
        evidence=[raw_doc_dict, higher_score_doc, sql_item],  # type: ignore[list-item]
    )

    result = collect_evidence(state)

    assert "evidence" in result
    evidence_list = result["evidence"]
    assert len(evidence_list) == 2  # Deduplicated from 3 to 2

    # Verify normalization to Evidence objects
    for item in evidence_list:
        assert isinstance(item, Evidence)

    # Verify highest score was retained for the duplicate locator
    doc_match = next(
        e
        for e in evidence_list
        if e.locator == "documents/adr-042-pgbouncer.md#chunk-0"
    )
    assert doc_match.score == 0.95
    assert "higher confidence" in doc_match.content

    # Verify metadata tracking
    assert result["metadata"]["evidence_count"] == 2
    assert result["metadata"]["deduplicated_count"] == 1
    assert result["current_node"] == "collect_evidence"


def test_collect_evidence_alias() -> None:
    """Test collect_evidence_node alias functions identically."""
    assert collect_evidence_node is collect_evidence


def test_collect_evidence_handles_empty_evidence() -> None:
    """Test collect_evidence behaves gracefully when evidence is empty."""
    state = ResearchState(
        session_id="test-session-empty",
        question="Sample empty query",
        evidence=[],
    )
    result = collect_evidence(state)
    assert result["evidence"] == []
    assert result["metadata"]["evidence_count"] == 0
    assert result["metadata"]["deduplicated_count"] == 0


def test_collect_evidence_with_dict_state() -> None:
    """Test collect_evidence accepts raw dictionary state."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-sess",
        "question": "Sample dict query",
        "evidence": [
            {
                "sub_question_id": "sq1",
                "source_type": "graph",
                "locator": "(Service:payments-api)-[:DEPENDS_ON]->(Database:core-db)",
                "content": "Payments API depends on core-db",
                "score": 1.0,
            }
        ],
        "metadata": {"existing_key": "val"},
    }
    result = collect_evidence(dict_state)
    assert len(result["evidence"]) == 1
    assert isinstance(result["evidence"][0], Evidence)
    assert result["metadata"]["existing_key"] == "val"
    assert result["metadata"]["evidence_count"] == 1


def test_collect_evidence_telemetry_resilience() -> None:
    """Test collect_evidence does not fail if tracer raises an exception."""
    state = ResearchState(
        session_id="test-telemetry-resilience",
        question="Query for tracer resilience",
        evidence=[],
    )
    with patch(
        "backend.app.core.observability.ObservabilityTracer.node",
        side_effect=RuntimeError("Tracer outage"),
    ):
        result = collect_evidence(state)
        assert result["evidence"] == []
        assert result["current_node"] == "collect_evidence"


# =============================================================================
# Node 7: check_missing_evidence Tests
# =============================================================================


def test_check_missing_evidence_all_covered() -> None:
    """Test when all sub-questions are covered, retry is False and missing_facets is empty."""
    sub_questions = [
        {"id": "sq1", "query": "What was the root cause?", "strategy": "vector"},
        {"id": "sq2", "query": "Which team owns it?", "strategy": "graph"},
    ]
    evidence = [
        create_document_evidence("sq1", "doc1.md", "Content 1"),
        create_graph_evidence("sq2", "(A)->(B)", "Content 2"),
    ]

    state = ResearchState(
        session_id="test-all-covered",
        question="Comprehensive question",
        sub_questions=sub_questions,
        evidence=evidence,
        corrective_rounds=0,
    )

    result = check_missing_evidence(state)

    assert result["missing_facets"] == []
    assert result["needs_retry"] is False
    assert result["metadata"]["missing_facets_count"] == 0
    assert result["current_node"] == "check_missing_evidence"


def test_corrective_retrieval_triggers_for_unanswerable_part() -> None:
    """F9 authoritative test: When a sub-question lacks evidence, triggers retry if rounds < MAX."""
    sub_questions = [
        {"id": "sq1", "query": "What was the root cause?", "strategy": "vector"},
        {
            "id": "sq2",
            "query": "What were the exact revenue loss numbers?",
            "strategy": "sql",
        },
    ]
    # Only sq1 has supporting evidence; sq2 is unbacked
    evidence = [
        create_document_evidence("sq1", "doc1.md", "Root cause is connection spike"),
    ]

    state = ResearchState(
        session_id="test-f9-corrective",
        question="What was root cause and revenue loss?",
        sub_questions=sub_questions,
        evidence=evidence,
        corrective_rounds=0,  # Round 0 < MAX_CORRECTIVE_ROUNDS (1)
    )

    result = check_missing_evidence(state)

    assert "sq2" in result["missing_facets"]
    assert len(result["missing_facets"]) == 1
    assert result["needs_retry"] is True
    assert result["metadata"]["missing_facets_count"] == 1
    assert result["metadata"]["needs_retry"] is True


def test_check_missing_evidence_bounded_loop_termination() -> None:
    """Verify corrective loop terminates when corrective_rounds >= MAX_CORRECTIVE_ROUNDS (1)."""
    sub_questions = [
        {"id": "sq1", "query": "What was the root cause?", "strategy": "vector"},
        {
            "id": "sq2",
            "query": "Unbacked facet that cannot be found",
            "strategy": "sql",
        },
    ]
    evidence = [
        create_document_evidence("sq1", "doc1.md", "Root cause is connection spike"),
    ]

    # corrective_rounds is already 1 (maximum permitted per Claude.md §7.3)
    state = ResearchState(
        session_id="test-bounded-loop",
        question="What was root cause and missing facet?",
        sub_questions=sub_questions,
        evidence=evidence,
        corrective_rounds=1,
    )

    result = check_missing_evidence(state)

    # Missing facets are still recorded accurately
    assert result["missing_facets"] == ["sq2"]
    # But needs_retry MUST be False to prevent infinite loops
    assert result["needs_retry"] is False
    assert result["metadata"]["needs_retry"] is False


def test_check_missing_evidence_alias() -> None:
    """Test check_missing_evidence_node alias functions identically."""
    assert check_missing_evidence_node is check_missing_evidence


def test_check_missing_evidence_with_dict_state() -> None:
    """Test check_missing_evidence works with plain dictionary state."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-missing",
        "question": "Sample query",
        "sub_questions": [{"id": "sq1", "query": "Query 1"}],
        "evidence": [],
        "corrective_rounds": 0,
        "metadata": {"initial": "val"},
    }
    result = check_missing_evidence(dict_state)
    assert result["missing_facets"] == ["sq1"]
    assert result["needs_retry"] is True
    assert result["metadata"]["initial"] == "val"


def test_check_missing_evidence_telemetry_resilience() -> None:
    """Test check_missing_evidence does not crash when tracer fails."""
    state = ResearchState(
        session_id="test-telemetry-fail",
        question="Query with broken tracer",
        sub_questions=[{"id": "sq1", "query": "Query 1"}],
        evidence=[create_document_evidence("sq1", "doc.md", "Text")],
        corrective_rounds=0,
    )
    with patch(
        "backend.app.core.observability.ObservabilityTracer.node",
        side_effect=RuntimeError("Tracer down"),
    ):
        result = check_missing_evidence(state)
        assert result["missing_facets"] == []
        assert result["needs_retry"] is False


# =============================================================================
# Sequential Pipeline Chaining Integration Test (Nodes 1-7)
# =============================================================================


def test_sequential_pipeline_nodes_1_to_7_canonical_question() -> None:
    """Test end-to-end chaining through Nodes 1 to 7 on the canonical test question."""
    initial_state = ResearchState(
        session_id="test-pipeline-nodes-1-to-7",
        question=CANONICAL_QUESTION_TEXT,
    )

    # Node 1: analyze_query
    s1 = analyze_query(initial_state)
    state = initial_state.model_copy(update=s1)

    # Node 2: assess_complexity
    s2 = assess_complexity(state)
    state = state.model_copy(update=s2)

    # Node 3: decompose
    s3 = decompose(state)
    state = state.model_copy(update=s3)

    # Node 4: route_retrieval
    s4 = route_retrieval(state)
    state = state.model_copy(update=s4)

    # Node 5: execute_retrieval
    s5 = execute_retrieval(state)
    state = state.model_copy(update=s5)

    # Node 6: collect_evidence
    s6 = collect_evidence(state)
    assert "evidence" in s6
    assert len(s6["evidence"]) > 0
    for e in s6["evidence"]:
        assert isinstance(e, Evidence)
        assert e.locator
        assert e.source_type in {"document", "sql", "graph"}
    state = state.model_copy(update=s6)

    # Node 7: check_missing_evidence
    s7 = check_missing_evidence(state)
    assert "missing_facets" in s7
    assert "needs_retry" in s7
    assert isinstance(s7["needs_retry"], bool)
    assert s7["current_node"] == "check_missing_evidence"
