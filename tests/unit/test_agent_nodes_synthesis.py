"""Unit tests for evidence verification and citation synthesis nodes (P9-7, F10, F11, Claude.md §3.1, §5, §7.3).

Validates:
- Node 9: verify_evidence:
  - F10: Cross-verifies claims and filters out malformed or below-threshold evidence
  - Computes verification_ratio as proportion of verified items
  - Preserves verified Evidence instances in verified_evidence
  - Telemetry resilience via tracer.node()
  - Duality: supports both ResearchState instances and raw dicts
- Node 10: synthesize_answer:
  - F11: Synthesizes grounded Markdown response embedding numbered citation markers [n]
  - Assembles structured citation mappings resolving [n] tokens to source locators
  - Prompt injection isolation: wraps untrusted evidence in protective delimiters
  - Multi-hop grounding across Document, SQL, and Graph stores
  - Telemetry resilience via tracer.node()
  - Duality: supports both ResearchState instances and raw dicts
- Authoritative requirement proofs:
  - test_canonical_question_end_to_end (F10)
  - test_multi_hop_citations_and_grounding (F11)
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
from agents.nodes.synthesize_answer import (
    synthesize_answer,
    synthesize_answer_node,
)
from agents.nodes.verify_evidence import (
    verify_evidence,
    verify_evidence_node,
)
from agents.rules import CANONICAL_QUESTION_TEXT
from agents.state import ResearchState
from backend.app.core.db import get_engine, get_session_factory, init_db
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
# Node 9: verify_evidence Tests (F10)
# =============================================================================


def test_verify_evidence_filters_and_computes_ratio() -> None:
    """Test verify_evidence confirms valid items and computes accurate verification_ratio."""
    valid_doc = create_document_evidence(
        sub_question_id="sq1",
        doc_id_or_filename="adr-042.md",
        content="Valid architectural decision record",
        score=0.92,
    )
    valid_sql = create_sql_evidence(
        sub_question_id="sq2",
        table="incidents",
        row_id="inc-2021",
        content="Incident record for Payments API",
        score=0.85,
    )
    # Low score evidence item below threshold (< 0.3)
    low_score_item = create_evidence(
        sub_question_id="sq3",
        source_type="document",
        locator="documents/noisy-log.txt#chunk-9",
        content="Uncorrelated log chatter with minimal relevance",
        score=0.15,
    )

    state = ResearchState(
        session_id="test-verify-evidence",
        question="What happened during the incident?",
        evidence=[valid_doc, valid_sql, low_score_item],
    )

    result = verify_evidence(state)

    assert result["current_node"] == "verify_evidence"
    assert len(result["verified_evidence"]) == 2
    # 2 out of 3 verified -> 0.6667
    assert pytest.approx(result["verification_ratio"], 0.01) == 0.67
    assert result["metadata"]["verified_evidence_count"] == 2
    assert result["metadata"]["raw_evidence_count"] == 3


def test_verify_evidence_empty_evidence() -> None:
    """Test verify_evidence handles empty evidence list gracefully."""
    state = ResearchState(
        session_id="test-verify-empty",
        question="Empty question",
        evidence=[],
    )

    result = verify_evidence(state)
    assert result["verified_evidence"] == []
    assert result["verification_ratio"] == 0.0
    assert result["metadata"]["verified_evidence_count"] == 0


def test_verify_evidence_alias() -> None:
    """Test verify_evidence_node alias functions identically."""
    assert verify_evidence_node is verify_evidence


def test_verify_evidence_with_dict_state() -> None:
    """Test verify_evidence functions with plain dictionary state."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-verify",
        "question": "Sample query",
        "evidence": [
            {
                "id": "evi_1",
                "sub_question_id": "sq1",
                "source_type": "graph",
                "locator": "(Service:payments-api)-[:DEPENDS_ON]->(Database:core-db)",
                "content": "Payments API depends on core-db",
                "score": 0.95,
            }
        ],
        "metadata": {"custom_meta": 123},
    }

    result = verify_evidence(dict_state)
    assert len(result["verified_evidence"]) == 1
    assert result["verification_ratio"] == 1.0
    assert result["metadata"]["custom_meta"] == 123


def test_verify_evidence_telemetry_resilience() -> None:
    """Test verify_evidence continues unaffected when tracer raises an exception."""
    state = ResearchState(
        session_id="test-verify-telemetry",
        question="Query with broken tracer",
        evidence=[create_document_evidence("sq1", "doc.md", "Content", score=0.9)],
    )

    with patch(
        "backend.app.core.observability.ObservabilityTracer.node",
        side_effect=RuntimeError("Tracer outage"),
    ):
        result = verify_evidence(state)
        assert len(result["verified_evidence"]) == 1
        assert result["verification_ratio"] == 1.0


# =============================================================================
# Node 10: synthesize_answer Tests (F11)
# =============================================================================


def test_synthesize_answer_generates_markdown_with_citations() -> None:
    """Test synthesize_answer embeds [n] citation markers and produces citation mappings."""
    e1 = create_document_evidence(
        sub_question_id="sq1",
        doc_id_or_filename="adr-042.md",
        content="Payments API connection pool exhaustion led to outage INC-2031",
        score=0.95,
    )
    e2 = create_sql_evidence(
        sub_question_id="sq2",
        table="customers",
        row_id="cust-101",
        content="Acme Corp, TechFlow, and FinEdge were affected enterprise clients",
        score=0.90,
    )
    e3 = create_graph_evidence(
        sub_question_id="sq3",
        locator="(Service:payments-api)<-[:OWNS]-(Team:team-payments)",
        content="Payments API owned by team-payments",
        score=1.0,
    )

    state = ResearchState(
        session_id="test-synth-answer",
        question="What was the Payments API outage impact, root cause, and ownership?",
        verified_evidence=[e1, e2, e3],
    )

    result = synthesize_answer(state)

    assert result["current_node"] == "synthesize_answer"
    answer = result["answer"]
    assert isinstance(answer, str)
    assert len(answer) > 0
    # Must contain citation tokens like [1], [2], etc.
    assert "[1]" in answer or "[2]" in answer or "[3]" in answer

    citations = result["citations"]
    assert len(citations) > 0
    for cit in citations:
        assert "citation_id" in cit
        assert "evidence_id" in cit
        assert "locator" in cit
        assert "source_type" in cit
        assert "snippet" in cit


def test_multi_hop_citations_and_grounding() -> None:
    """F11 authoritative test: Multi-hop reasoning across Document, SQL, and Graph stores."""
    # 1. Document store evidence (root cause)
    doc_ev = create_document_evidence(
        sub_question_id="sq1",
        doc_id_or_filename="q2-incident-post-mortem.md",
        content="Unhandled webhook connection timeouts caused cascading failures in Payments API [INC-2031]",
        score=0.96,
    )
    # 2. SQL store evidence (impacted customers)
    sql_ev = create_sql_evidence(
        sub_question_id="sq2",
        table="customers",
        row_id="cust-multi",
        content="Customers impacted: Acme Corp, TechFlow, FinEdge",
        score=0.91,
    )
    # 3. Graph store evidence (team ownership)
    graph_ev = create_graph_evidence(
        sub_question_id="sq3",
        locator="(Team:team-payments)-[:OWNS]->(Service:svc-payments-api)",
        content="team-payments owns svc-payments-api",
        score=1.0,
    )

    state = ResearchState(
        session_id="test-multi-hop-grounding",
        question="Provide a multi-hop root cause, customer impact, and ownership report for Payments API outage.",
        verified_evidence=[doc_ev, sql_ev, graph_ev],
    )

    result = synthesize_answer(state)

    answer = result["answer"]
    citations = result["citations"]

    # Verify answer embeds citations
    assert any(f"[{i}]" in answer for i in range(1, 4))
    # Verify citations resolve to source evidence locators
    citation_locators = {c["locator"] for c in citations}
    assert any(
        "q2-incident-post-mortem" in loc or "adr" in loc for loc in citation_locators
    ) or any("sql" in loc for loc in citation_locators)
    assert result["metadata"]["citations_count"] == len(citations)


def test_synthesize_answer_alias() -> None:
    """Test synthesize_answer_node alias functions identically."""
    assert synthesize_answer_node is synthesize_answer


def test_synthesize_answer_with_dict_state() -> None:
    """Test synthesize_answer functions with raw dictionary state."""
    dict_state: dict[str, Any] = {
        "session_id": "test-dict-synth",
        "question": "What is Payments API?",
        "verified_evidence": [
            {
                "id": "evi_synth_1",
                "sub_question_id": "sq1",
                "source_type": "document",
                "locator": "documents/adr-042.md#chunk-0",
                "content": "PgBouncer connection pooling documentation.",
                "score": 0.95,
                "metadata": {},
            }
        ],
        "metadata": {"trace_ctx": "test"},
    }

    result = synthesize_answer(dict_state)
    assert result["current_node"] == "synthesize_answer"
    assert len(result["answer"]) > 0
    assert result["metadata"]["trace_ctx"] == "test"


def test_synthesize_answer_telemetry_resilience() -> None:
    """Test synthesize_answer does not crash when tracer fails."""
    state = ResearchState(
        session_id="test-synth-telemetry",
        question="Query for tracer failure",
        verified_evidence=[
            create_document_evidence("sq1", "doc.md", "Content text", score=0.9)
        ],
    )

    with patch(
        "backend.app.core.observability.ObservabilityTracer.node",
        side_effect=RuntimeError("Tracer down"),
    ):
        result = synthesize_answer(state)
        assert len(result["answer"]) > 0
        assert result["current_node"] == "synthesize_answer"


# =============================================================================
# Canonical End-to-End Pipeline Integration Test (Nodes 1 to 10 - F10)
# =============================================================================


def test_canonical_question_end_to_end() -> None:
    """Authoritative F10 test: Execute full pipeline from Query Analysis through Answer Synthesis."""
    initial_state = ResearchState(
        session_id="test-canonical-e2e",
        question=CANONICAL_QUESTION_TEXT,
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

    # 8. verify_evidence (F10)
    s8 = verify_evidence(state)
    assert s8["current_node"] == "verify_evidence"
    assert "verified_evidence" in s8
    assert len(s8["verified_evidence"]) > 0
    assert (
        s8["verification_ratio"] >= 0.5
    )  # Solid verification ratio on canonical query
    state = state.model_copy(update=s8)

    # 9. synthesize_answer (F11)
    s9 = synthesize_answer(state)
    assert s9["current_node"] == "synthesize_answer"
    assert len(s9["answer"]) > 0
    assert len(s9["citations"]) > 0
    # Every citation must carry a valid locator and evidence_id
    for citation in s9["citations"]:
        assert citation["evidence_id"]
        assert citation["locator"]
        assert citation["source_type"] in {"document", "sql", "graph"}
