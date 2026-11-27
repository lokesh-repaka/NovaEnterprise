"""Unit tests for bounded corrective retrieval loop node (P9-6, F9, Claude.md §3.1, §5, §7.3, FRD §5.2).

Validates:
- Node 8: corrective_retrieval:
  - Detects unbacked sub-questions from missing_facets
  - Reformulates sub-queries with expanded synonyms and broadened search terms
  - Re-executes retrieval using appropriate strategies
  - Increments corrective_rounds to bound loop execution (MAX_CORRECTIVE_ROUNDS=1)
  - Authoritative F9 test: test_corrective_retrieval_triggers_for_unanswerable_part
  - Bounded termination: guarantees loop does not exceed MAX_CORRECTIVE_ROUNDS
  - Telemetry resilience via tracer.node() and tracer.record_query()
  - Duality: supports both ResearchState models and raw state dicts
  - Loop integration: executes check_missing_evidence -> corrective_retrieval -> collect_evidence -> check_missing_evidence
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agents.nodes.check_missing_evidence import check_missing_evidence
from agents.nodes.collect_evidence import collect_evidence
from agents.nodes.corrective_retrieval import (
    corrective_retrieval,
    corrective_retrieval_node,
    reformulate_query,
)
from agents.state import ResearchState
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.services.seed import seed_database
from rag.evidence import create_evidence
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
                "id": "chunk-postmortem-pm2026",
                "document_id": "doc-pm2026",
                "text": "Executive Q2 incident post-mortem: Payments API experienced cascading timeouts due to connection exhaustion.",
                "metadata": {
                    "source": "documents/q2-incident-post-mortem.md",
                    "chunk_index": 1,
                },
            },
            {
                "id": "chunk-synonyms-remediation",
                "document_id": "doc-remediation",
                "text": "Mitigation steps and remediation actions for Payments API service outages include connection pool limits and circuit breakers.",
                "metadata": {
                    "source": "documents/mitigation-actions.md",
                    "chunk_index": 0,
                },
            },
        ]
        v_store.add_documents(sample_chunks)
        HybridRetriever(vector_store=v_store).index_chunks(sample_chunks)

    yield


# =============================================================================
# Helper function tests
# =============================================================================


def test_reformulate_query_broadens_terms() -> None:
    """Test reformulate_query expands synonyms and adds broader recovery terms."""
    original = "What was the failure in Payments API?"
    reformulated = reformulate_query(original, target_entity="Payments API")

    assert reformulated != original
    assert len(reformulated) > len(original)
    # Check that helpful retrieval keywords were appended
    assert any(
        term in reformulated.lower()
        for term in ("incident", "outage", "postmortem", "root cause", "mitigation")
    )


# =============================================================================
# Node 8: corrective_retrieval Tests
# =============================================================================


def test_corrective_retrieval_rephrases_and_retrieves() -> None:
    """Test corrective retrieval reformulates missing sub-questions and retrieves evidence."""
    sub_questions = [
        {"id": "sq1", "question": "What is Payments API?", "strategy": "vector"},
        {
            "id": "sq2",
            "question": "What remediation actions were taken?",
            "strategy": "vector",
        },
    ]
    # sq1 already has evidence; sq2 is in missing_facets
    initial_evidence = [
        create_evidence(
            sub_question_id="sq1",
            source_type="document",
            locator="documents/adr-042-pgbouncer.md#chunk-0",
            content="PgBouncer connection pooling documentation.",
            score=0.9,
        )
    ]

    state = ResearchState(
        session_id="test-corrective-run",
        question="Payments API architecture and remediation actions",
        entity="Payments API",
        sub_questions=sub_questions,
        evidence=initial_evidence,
        missing_facets=["sq2"],
        corrective_rounds=0,
        needs_retry=True,
    )

    result = corrective_retrieval(state)

    assert result["current_node"] == "corrective_retrieval"
    assert result["corrective_rounds"] == 1
    assert result["needs_retry"] is False

    # Check evidence was retrieved for the missing facet sq2
    new_evidence = result["evidence"]
    assert len(new_evidence) > len(initial_evidence)
    assert any(e.sub_question_id == "sq2" for e in new_evidence)

    # Check sub_questions were updated with reformulated query
    updated_sq2 = next(sq for sq in result["sub_questions"] if sq["id"] == "sq2")
    assert updated_sq2.get("reformulated") is True
    assert updated_sq2["question"] != "What remediation actions were taken?"


def test_corrective_retrieval_triggers_for_unanswerable_part() -> None:
    """F9 authoritative test: When a sub-question is unanswerable, corrective round executes once and terminates."""
    sub_questions = [
        {"id": "sq1", "question": "What is Payments API?", "strategy": "vector"},
        {
            "id": "sq2",
            "question": "Completely non-existent extraterrestrial alien data that cannot be found anywhere",
            "strategy": "vector",
        },
    ]
    initial_evidence = [
        create_evidence(
            sub_question_id="sq1",
            source_type="document",
            locator="documents/adr-042-pgbouncer.md#chunk-0",
            content="PgBouncer connection pooling.",
            score=0.9,
        )
    ]

    state = ResearchState(
        session_id="test-unanswerable-part",
        question="What is Payments API and extraterrestrial data?",
        sub_questions=sub_questions,
        evidence=initial_evidence,
        missing_facets=["sq2"],
        corrective_rounds=0,
        needs_retry=True,
    )

    result = corrective_retrieval(state)

    # Corrective rounds incremented to 1
    assert result["corrective_rounds"] == 1
    # needs_retry set to False to terminate loop
    assert result["needs_retry"] is False
    assert result["metadata"]["corrective_iterations"] == 1


def test_corrective_retrieval_bounds_at_max_rounds() -> None:
    """Test that corrective retrieval respects MAX_CORRECTIVE_ROUNDS and does not re-run if already at limit."""
    sub_questions = [{"id": "sq1", "question": "Unbacked facet", "strategy": "vector"}]
    state = ResearchState(
        session_id="test-max-rounds",
        question="Unbacked query",
        sub_questions=sub_questions,
        evidence=[],
        missing_facets=["sq1"],
        corrective_rounds=1,  # Already at MAX_CORRECTIVE_ROUNDS (1)
        needs_retry=False,
    )

    result = corrective_retrieval(state)

    # Does not run additional retrievals when already at max rounds
    assert result["corrective_rounds"] == 1
    assert result["needs_retry"] is False
    assert result["metadata"].get("skipped_max_rounds") is True


def test_corrective_retrieval_alias() -> None:
    """Test corrective_retrieval_node alias is identical to corrective_retrieval."""
    assert corrective_retrieval_node is corrective_retrieval


def test_corrective_retrieval_with_dict_state() -> None:
    """Test corrective retrieval functions with raw dictionary state."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-corrective",
        "question": "Payments API remediation",
        "entity": "Payments API",
        "sub_questions": [
            {
                "id": "sq1",
                "question": "Remediation actions taken",
                "strategy": "vector",
            }
        ],
        "evidence": [],
        "missing_facets": ["sq1"],
        "corrective_rounds": 0,
        "needs_retry": True,
        "metadata": {"prev": "data"},
    }

    result = corrective_retrieval(dict_state)
    assert result["current_node"] == "corrective_retrieval"
    assert result["corrective_rounds"] == 1
    assert result["metadata"]["prev"] == "data"
    assert len(result["evidence"]) > 0


def test_corrective_retrieval_telemetry_resilience() -> None:
    """Test corrective retrieval does not raise when tracer fails."""
    state = ResearchState(
        session_id="test-tracer-failure",
        question="Query with broken tracer",
        sub_questions=[{"id": "sq1", "question": "Query", "strategy": "vector"}],
        missing_facets=["sq1"],
        corrective_rounds=0,
    )

    with patch(
        "backend.app.core.observability.ObservabilityTracer.node",
        side_effect=RuntimeError("Tracer failure"),
    ):
        result = corrective_retrieval(state)
        assert result["current_node"] == "corrective_retrieval"
        assert result["corrective_rounds"] == 1


# =============================================================================
# Sequential Bounded Corrective Loop Integration Test
# =============================================================================


def test_bounded_corrective_loop_complete_flow() -> None:
    """Test end-to-end corrective loop flow:

    check_missing_evidence (detects missing)
    -> corrective_retrieval (reformulates, retrieves, increments rounds)
    -> collect_evidence (merges and dedupes)
    -> check_missing_evidence (verifies bounds: rounds=1 -> needs_retry=False)
    """
    sub_questions = [
        {"id": "sq1", "question": "What is Payments API?", "strategy": "vector"},
        {
            "id": "sq2",
            "question": "What remediation actions were taken?",
            "strategy": "vector",
        },
    ]
    # Initially only sq1 has evidence
    initial_evidence = [
        create_evidence(
            sub_question_id="sq1",
            source_type="document",
            locator="documents/adr-042-pgbouncer.md#chunk-0",
            content="PgBouncer connection pooling documentation.",
            score=0.9,
        )
    ]

    state = ResearchState(
        session_id="test-loop-flow",
        question="Payments API architecture and remediation",
        entity="Payments API",
        sub_questions=sub_questions,
        evidence=initial_evidence,
        corrective_rounds=0,
    )

    # 1. First check_missing_evidence: detects sq2 missing
    chk1 = check_missing_evidence(state)
    assert chk1["missing_facets"] == ["sq2"]
    assert chk1["needs_retry"] is True
    state = state.model_copy(update=chk1)

    # 2. corrective_retrieval: executes reformulation and re-retrieval for sq2
    corr = corrective_retrieval(state)
    assert corr["corrective_rounds"] == 1
    state = state.model_copy(update=corr)

    # 3. collect_evidence: merges and deduplicates
    coll = collect_evidence(state)
    assert len(coll["evidence"]) >= 2
    state = state.model_copy(update=coll)

    # 4. Second check_missing_evidence: rounds == 1 -> loop MUST terminate!
    chk2 = check_missing_evidence(state)
    assert chk2["needs_retry"] is False
    assert chk2["metadata"]["needs_retry"] is False
