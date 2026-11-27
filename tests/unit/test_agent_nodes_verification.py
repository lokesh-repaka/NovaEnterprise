"""Unit tests for citation verification and memory update nodes (P9-8, F12, F15, Claude.md §3.1, §5, §7.3).

Validates:
- Node 11: verify_citations:
  - F12: Verifies each [n] citation marker resolves to existing evidence
  - Detects and strips invalid / unresolvable citation tokens from synthesized answer text
  - Filters out unresolvable citation records from citations array
  - Populates unresolved_citations list and citations_verified boolean
  - Telemetry resilience via tracer.node()
  - Duality: supports both ResearchState instances and raw dicts
- Node 12: update_memory:
  - F15: Records completed interaction turn into episodic memory
  - Transitions workflow state status to 'completed'
  - Telemetry resilience via tracer.node()
  - Aliases: update_memory_node, memory_update, memory_update_node
  - Duality: supports both ResearchState instances and raw dicts
- Authoritative requirement proofs:
  - test_research_lifecycle (F12, F15): validates citation resolution and memory persistence across full lifecycle
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agents.nodes.analyze_query import analyze_query
from agents.nodes.assess_complexity import assess_complexity
from agents.nodes.check_missing_evidence import check_missing_evidence
from agents.nodes.collect_evidence import collect_evidence
from agents.nodes.decompose import decompose
from agents.nodes.execute_retrieval import execute_retrieval
from agents.nodes.route_retrieval import route_retrieval
from agents.nodes.synthesize_answer import synthesize_answer
from agents.nodes.update_memory import (
    memory_update,
    memory_update_node,
    update_memory,
    update_memory_node,
)
from agents.nodes.verify_citations import (
    verify_citations,
    verify_citations_node,
)
from agents.nodes.verify_evidence import verify_evidence
from agents.rules import CANONICAL_QUESTION_TEXT
from agents.state import ResearchState
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.services.seed import seed_database
from memory.memory_service import get_memory_service, reset_memory_service
from memory.protocols import InMemoryEpisodicMemoryStore
from rag.evidence import (
    create_document_evidence,
    create_sql_evidence,
)
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store
from rag.retriever import HybridRetriever
from rag.vector_store import InMemoryVectorStore, get_vector_store


@pytest.fixture(autouse=True)
def setup_test_environment() -> Any:
    """Initialize in-memory stores and reset memory service for offline test isolation."""
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

    # 4. In-memory episodic store for memory service
    reset_memory_service()
    mem_service = get_memory_service(episodic_store=InMemoryEpisodicMemoryStore())

    yield mem_service
    reset_memory_service()


# =============================================================================
# Node 11: verify_citations Tests (F12)
# =============================================================================


def test_verify_citations_all_valid() -> None:
    """Test verify_citations confirms all citations when tokens map to existing evidence."""
    evidence = [
        create_document_evidence("sq1", "adr-042.md", "Content 1", score=0.9),
        create_sql_evidence(
            "sq2", "customers", "Content 2", row_id="cust-1", score=0.9
        ),
    ]
    citations = [
        {
            "citation_id": 1,
            "evidence_id": evidence[0].id,
            "source_type": "document",
            "locator": evidence[0].locator,
            "snippet": "Content 1",
        },
        {
            "citation_id": 2,
            "evidence_id": evidence[1].id,
            "source_type": "sql",
            "locator": evidence[1].locator,
            "snippet": "Content 2",
        },
    ]
    answer = "Payments API architecture relies on PgBouncer [1] impacting enterprise customers [2]."

    state = ResearchState(
        session_id="test-citations-valid",
        question="What is the architecture?",
        answer=answer,
        evidence=evidence,
        citations=citations,
    )

    result = verify_citations(state)

    assert result["current_node"] == "verify_citations"
    assert result["unresolved_citations"] == []
    assert result["citations_verified"] is True
    assert result["answer"] == answer
    assert len(result["citations"]) == 2


def test_verify_citations_strips_invalid_tokens() -> None:
    """Test verify_citations detects and strips unresolvable [n] markers from answer text."""
    evidence = [
        create_document_evidence("sq1", "adr-042.md", "Content 1", score=0.9),
    ]
    citations = [
        {
            "citation_id": 1,
            "evidence_id": evidence[0].id,
            "source_type": "document",
            "locator": evidence[0].locator,
            "snippet": "Content 1",
        },
        {
            "citation_id": 99,
            "evidence_id": "evi_nonexistent",
            "source_type": "sql",
            "locator": "sql:unknown",
            "snippet": "Phantom citation",
        },
    ]
    # Answer contains valid [1] and invalid [99] and [42]
    answer = (
        "Valid claim [1] followed by hallucinated claim [99] and phantom data [42]."
    )

    state = ResearchState(
        session_id="test-citations-invalid",
        question="Query with invalid citations",
        answer=answer,
        evidence=evidence,
        citations=citations,
    )

    result = verify_citations(state)

    assert result["current_node"] == "verify_citations"
    assert 99 in result["unresolved_citations"]
    assert 42 in result["unresolved_citations"]
    assert result["citations_verified"] is False

    # Invalid tokens stripped from answer
    sanitized = result["answer"]
    assert "[1]" in sanitized
    assert "[99]" not in sanitized
    assert "[42]" not in sanitized

    # Unresolvable citation record removed from citations list
    verified_cits = result["citations"]
    assert len(verified_cits) == 1
    assert verified_cits[0]["citation_id"] == 1


def test_verify_citations_empty_citations() -> None:
    """Test verify_citations handles answer with zero citation tokens cleanly."""
    state = ResearchState(
        session_id="test-citations-empty",
        question="Query without citations",
        answer="Plain factual answer with no citations.",
        evidence=[],
        citations=[],
    )

    result = verify_citations(state)
    assert result["unresolved_citations"] == []
    assert result["citations_verified"] is True
    assert result["answer"] == "Plain factual answer with no citations."


def test_verify_citations_alias() -> None:
    """Test verify_citations_node alias functions identically."""
    assert verify_citations_node is verify_citations


def test_verify_citations_with_dict_state() -> None:
    """Test verify_citations functions with raw dictionary state."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-citations",
        "question": "Sample dict query",
        "answer": "Grounded statement [1].",
        "evidence": [
            {
                "id": "evi-1",
                "sub_question_id": "sq1",
                "source_type": "document",
                "locator": "documents/doc.md",
                "content": "Doc content",
                "score": 0.9,
            }
        ],
        "citations": [
            {"citation_id": 1, "evidence_id": "evi-1", "locator": "documents/doc.md"}
        ],
        "metadata": {"test_meta": True},
    }

    result = verify_citations(dict_state)
    assert result["unresolved_citations"] == []
    assert result["citations_verified"] is True
    assert result["metadata"]["test_meta"] is True


def test_verify_citations_telemetry_resilience() -> None:
    """Test verify_citations does not fail when tracer throws an error."""
    state = ResearchState(
        session_id="test-telemetry-citations",
        question="Query with broken tracer",
        answer="Answer [1]",
        evidence=[create_document_evidence("sq1", "doc.md", "Content", score=0.9)],
    )

    with patch(
        "backend.app.core.observability.ObservabilityTracer.node",
        side_effect=RuntimeError("Tracer outage"),
    ):
        result = verify_citations(state)
        assert result["citations_verified"] is True
        assert result["current_node"] == "verify_citations"


# =============================================================================
# Node 12: update_memory Tests (F15)
# =============================================================================


def test_update_memory_records_turn_and_completes() -> None:
    """Test update_memory records interaction turn in episodic memory and completes workflow."""
    session_id = "test-mem-session-123"
    question = "What was the Payments API outage impact?"
    answer = "Three enterprise clients were impacted [1]."
    citations = [{"citation_id": 1, "locator": "sql:customers:101"}]

    state = ResearchState(
        session_id=session_id,
        question=question,
        answer=answer,
        citations=citations,
        complexity="moderate",
        user_id="analyst-42",
        status="running",
    )

    result = update_memory(state)

    assert result["current_node"] == "update_memory"
    assert result["status"] == "completed"
    assert result["metadata"]["memory_updated"] is True

    # Verify episodic entry was written to memory service
    mem_service = get_memory_service()
    history = mem_service.get_episodic_history(session_id)
    assert len(history) == 1
    assert history[0].question == question
    assert history[0].answer == answer
    assert history[0].user_id == "analyst-42"
    assert "sql:customers:101" in history[0].citations


def test_update_memory_aliases() -> None:
    """Test update_memory aliases function identically."""
    assert update_memory_node is update_memory
    assert memory_update is update_memory
    assert memory_update_node is update_memory


def test_update_memory_with_dict_state() -> None:
    """Test update_memory operates with raw dictionary state."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-mem-sess",
        "question": "Dict memory question",
        "answer": "Dict memory answer",
        "citations": [],
        "complexity": "simple",
        "user_id": "user-demo",
        "metadata": {"existing": 123},
    }

    result = update_memory(dict_state)
    assert result["status"] == "completed"
    assert result["metadata"]["existing"] == 123
    assert result["metadata"]["memory_updated"] is True


def test_update_memory_telemetry_resilience() -> None:
    """Test update_memory continues even if tracer raises an exception."""
    state = ResearchState(
        session_id="test-mem-tracer-fail",
        question="Query",
        answer="Answer",
    )

    with patch(
        "backend.app.core.observability.ObservabilityTracer.node",
        side_effect=RuntimeError("Tracer down"),
    ):
        result = update_memory(state)
        assert result["status"] == "completed"
        assert result["current_node"] == "update_memory"


# =============================================================================
# Full Research Lifecycle Integration Test (F12, F15)
# =============================================================================


def test_research_lifecycle() -> None:
    """Authoritative F12 & F15 test: Execute full research workflow through citation verification and memory update."""
    initial_state = ResearchState(
        session_id="test-lifecycle-full-session",
        question=CANONICAL_QUESTION_TEXT,
        user_id="lead-architect",
    )

    # 1. analyze_query
    s1 = analyze_query(initial_state)
    state = initial_state.model_copy(update=s1)

    # 2. assess_complexity
    s2 = assess_complexity(state)
    state = state.model_copy(update=s2)

    # 3. decompose
    s3 = decompose(state)
    state = state.model_copy(update=s3)

    # 4. route_retrieval
    s4 = route_retrieval(state)
    state = state.model_copy(update=s4)

    # 5. execute_retrieval
    s5 = execute_retrieval(state)
    state = state.model_copy(update=s5)

    # 6. collect_evidence
    s6 = collect_evidence(state)
    state = state.model_copy(update=s6)

    # 7. check_missing_evidence
    s7 = check_missing_evidence(state)
    state = state.model_copy(update=s7)

    # 8. verify_evidence
    s8 = verify_evidence(state)
    state = state.model_copy(update=s8)

    # 9. synthesize_answer
    s9 = synthesize_answer(state)
    state = state.model_copy(update=s9)

    # 10. verify_citations (F12)
    s10 = verify_citations(state)
    assert s10["current_node"] == "verify_citations"
    assert s10["unresolved_citations"] == []
    assert s10["citations_verified"] is True
    assert len(s10["citations"]) > 0
    state = state.model_copy(update=s10)

    # 11. update_memory (F15)
    s11 = update_memory(state)
    assert s11["current_node"] == "update_memory"
    assert s11["status"] == "completed"
    state = state.model_copy(update=s11)

    # Final Lifecycle State Invariants
    assert state.status == "completed"
    assert len(state.answer) > 0
    assert len(state.citations) > 0

    # Verify episodic entry in memory facade
    mem_service = get_memory_service()
    entries = mem_service.get_episodic_history("test-lifecycle-full-session")
    assert len(entries) >= 1
    assert entries[0].user_id == "lead-architect"
    assert len(entries[0].citations) > 0
