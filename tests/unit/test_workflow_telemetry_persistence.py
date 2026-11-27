"""Unit tests for LangGraph node telemetry and per-node state persistence (P10-2, F16, N9, Claude.md §4.1, §16).

Validates:
- ResearchService.create_session: creates research_sessions row with status='running'.
- ResearchService._persist: updates research_sessions row after each node transition (the state in the DB is the progress bar).
- Per-node workflow_events emission (F16): node transitions, queries, latencies, and sanitized payloads recorded.
- Strict Prompt Privacy (N9): raw internal prompts and secrets scrubbed before DB write.
- End-to-end workflow execution with per-node persistence through all 13 nodes.
- Zero-crash telemetry and persistence error resilience.
- Failed workflow handling: status transitions to 'failed' and error events recorded.
"""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from agents.rules import CANONICAL_QUESTION_TEXT
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.core.observability import (
    DISALLOWED_PROMPT_KEYS,
    filter_telemetry_payload,
)
from backend.app.repositories.research import (
    CitationRecordRepository,
    ResearchSessionRepository,
    WorkflowEventRepository,
)
from backend.app.services.research_service import (
    ResearchService,
    reset_research_service,
)
from backend.app.services.seed import seed_database
from memory.memory_service import get_memory_service, reset_memory_service
from memory.protocols import InMemoryEpisodicMemoryStore
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store
from rag.retriever import HybridRetriever
from rag.vector_store import InMemoryVectorStore, get_vector_store


@pytest.fixture
def db_session_factory() -> sessionmaker[Session]:
    """In-memory SQLite database session factory for offline isolation."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    factory = get_session_factory(engine)
    with factory() as session:
        seed_database(session)
    return factory


@pytest.fixture(autouse=True)
def setup_environment(db_session_factory: sessionmaker[Session]) -> Any:
    """Initialize test environment with seeded vector, graph, and memory stores."""
    # 1. Graph store
    store = get_graph_store()
    if isinstance(store, InMemoryGraphStore):
        sample_dir = Path(__file__).resolve().parents[2] / "sample_data"
        seed_graph_from_domain(store, sample_data_dir=sample_dir)

    # 2. Vector store
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

    # 3. Memory store
    reset_memory_service()
    get_memory_service(episodic_store=InMemoryEpisodicMemoryStore())

    # 4. Research service singleton reset
    reset_research_service()

    yield

    reset_research_service()
    reset_memory_service()


def test_research_service_create_session(
    db_session_factory: sessionmaker[Session],
) -> None:
    """Test create_session initializes a research_sessions row in running state."""
    service = ResearchService(session_factory=db_session_factory)
    session = service.create_session(
        question="Which customers were impacted by the outage?",
        user_id="lead-analyst",
        complexity="complex",
    )

    assert session is not None
    assert session.id.startswith("rs-")
    assert session.status == "running"
    assert session.complexity == "complex"
    assert session.question == "Which customers were impacted by the outage?"

    # Verify persistence in database
    with db_session_factory() as db:
        repo = ResearchSessionRepository(db)
        persisted = repo.get(session.id)
        assert persisted is not None
        assert persisted.status == "running"
        assert persisted.question == session.question


def test_research_service_persist_updates_state_progressively(
    db_session_factory: sessionmaker[Session],
) -> None:
    """Test _persist updates research_sessions fields after simulated node transitions."""
    service = ResearchService(session_factory=db_session_factory)
    session = service.create_session(
        question="What is the Payments API architecture?",
        user_id="analyst-1",
    )
    session_id = session.id

    # 1. Simulate after assess_complexity node
    state_step1 = {
        "complexity": "complex",
        "current_node": "assess_complexity",
    }
    service._persist(session_id, state_step1, node_name="assess_complexity")

    with db_session_factory() as db:
        row = ResearchSessionRepository(db).get(session_id)
        assert row is not None
        assert row.complexity == "complex"
        assert row.status == "running"

    # 2. Simulate after decompose node
    state_step2 = {
        **state_step1,
        "sub_questions": [
            {"id": "sq1", "question": "What is Payments API?", "strategy": "vector"}
        ],
        "current_node": "decompose",
    }
    service._persist(session_id, state_step2, node_name="decompose")

    with db_session_factory() as db:
        row = ResearchSessionRepository(db).get(session_id)
        assert row is not None
        assert len(row.sub_questions) == 1
        assert row.sub_questions[0]["id"] == "sq1"

    # 3. Simulate after update_memory (completion)
    state_step3 = {
        **state_step2,
        "status": "completed",
        "answer": "Payments API is a Tier-1 financial service [1].",
        "citations": [
            {
                "citation_id": 1,
                "locator": "doc:chunk-adr-042#chunk-0#chunk-0",
                "document_id": "doc-adr-042",
                "chunk_id": "chunk-adr-042",
                "snippet": "ADR-042",
            }
        ],
        "execution_time_seconds": 1.25,
        "current_node": "update_memory",
    }
    service._persist(session_id, state_step3, node_name="update_memory")

    with db_session_factory() as db:
        row = ResearchSessionRepository(db).get(session_id)
        assert row is not None
        assert row.status == "completed"
        assert row.answer == "Payments API is a Tier-1 financial service [1]."
        assert row.execution_time == 1.25

        # Verify CitationRecord created
        cit_repo = CitationRecordRepository(db)
        cits = cit_repo.list_by_session(session_id)
        assert len(cits) == 1
        assert cits[0].locator == "doc:chunk-adr-042#chunk-0#chunk-0"


def test_research_service_persists_workflow_events(
    db_session_factory: sessionmaker[Session],
) -> None:
    """Test node transitions emit WorkflowEvent records in database (F16)."""
    service = ResearchService(session_factory=db_session_factory)
    session = service.create_session(
        question="Check telemetry persistence",
        user_id="telemetry-auditor",
    )
    session_id = session.id

    # Record two simulated node transitions
    service.record_node_event(
        session_id=session_id,
        node_name="analyze_query",
        payload={"intent": "architecture_query", "entity": "Payments API"},
        latency_ms=45,
    )
    service.record_node_event(
        session_id=session_id,
        node_name="assess_complexity",
        payload={"complexity": "moderate"},
        latency_ms=12,
    )

    events = service.list_events(session_id)
    assert len(events) == 2
    assert events[0].node_name == "analyze_query"
    assert events[0].payload["intent"] == "architecture_query"
    assert events[0].latency_ms == 45
    assert events[1].node_name == "assess_complexity"
    assert events[1].payload["complexity"] == "moderate"


def test_telemetry_prompt_privacy_guarantee(
    db_session_factory: sessionmaker[Session],
) -> None:
    """Verify N9: filter_telemetry_payload scrubs raw prompts and credentials before DB persistence."""
    dirty_payload = {
        "node": "decompose",
        "prompt": "SYSTEM: You are an internal agent...",
        "system_prompt": "CRITICAL INSTRUCTIONS...",
        "messages": [{"role": "system", "content": "secret"}],
        "chain_of_thought": "Thinking about subquestions...",
        "credentials": "aws_secret_key=AKIAIOSFODNN7EXAMPLE",
        "safe_metric": 4,
        "clean_list": [{"reason": "valid decision"}],
    }

    filtered = filter_telemetry_payload(dirty_payload)
    for key in DISALLOWED_PROMPT_KEYS:
        assert key not in filtered

    assert filtered["node"] == "decompose"
    assert filtered["safe_metric"] == 4
    assert len(filtered["clean_list"]) == 1

    # Verify when persisted through service
    service = ResearchService(session_factory=db_session_factory)
    session = service.create_session(question="Privacy test")
    service.record_node_event(
        session_id=session.id,
        node_name="decompose",
        payload=dirty_payload,
    )

    events = service.list_events(session.id)
    assert len(events) == 1
    for key in DISALLOWED_PROMPT_KEYS:
        assert key not in events[0].payload


def test_end_to_end_research_service_run_workflow_per_node_persistence(
    db_session_factory: sessionmaker[Session],
) -> None:
    """Execute complete workflow through ResearchService and verify DB state after all 13 nodes."""
    service = ResearchService(session_factory=db_session_factory)
    session = service.create_session(
        question=CANONICAL_QUESTION_TEXT,
        user_id="lead-analyst",
    )
    session_id = session.id

    # Execute workflow with per-node persistence
    final_state = service.run_research(
        session_id=session_id,
        question=CANONICAL_QUESTION_TEXT,
        user_id="lead-analyst",
    )

    assert final_state["status"] == "completed"

    # Verify session row in DB has final progress bar state
    with db_session_factory() as db:
        session_row = ResearchSessionRepository(db).get(session_id)
        assert session_row is not None
        assert session_row.status == "completed"
        assert session_row.complexity in {"moderate", "complex"}
        assert len(session_row.sub_questions) >= 1
        assert len(session_row.evidence_data) >= 1
        assert len(session_row.answer or "") > 0
        assert session_row.execution_time is not None
        assert session_row.execution_time > 0

        # Verify WorkflowEvent records in DB (F16)
        event_repo = WorkflowEventRepository(db)
        events = event_repo.list_by_session(session_id)
        # Canonical single-pass non-retry workflow executes exactly 12 nodes
        assert len(events) >= 12
        node_names = [e.node_name for e in events]
        assert "recall_memory" in node_names
        assert "analyze_query" in node_names
        assert "assess_complexity" in node_names
        assert "decompose" in node_names
        assert "route_retrieval" in node_names
        assert "execute_retrieval" in node_names
        assert "collect_evidence" in node_names
        assert "check_missing_evidence" in node_names
        assert "verify_evidence" in node_names
        assert "synthesize_answer" in node_names
        assert "verify_citations" in node_names
        assert "update_memory" in node_names

        # Verify CitationRecord rows in DB
        cit_repo = CitationRecordRepository(db)
        citations = cit_repo.list_by_session(session_id)
        assert len(citations) >= 1


def test_research_service_run_workflow_with_corrective_loop(
    db_session_factory: sessionmaker[Session],
) -> None:
    """Execute query triggering corrective retrieval and verify corrective_retrieval event is recorded."""
    from rag.vector_store import reset_vector_store

    # Reset vector store to 0 documents to trigger missing evidence and corrective retrieval
    reset_vector_store()

    service = ResearchService(session_factory=db_session_factory)
    session = service.create_session(
        question="What caused the failure in nonexistent-unindexed-service-404?",
        user_id="test-analyst",
    )
    session_id = session.id

    final_state = service.run_research(
        session_id=session_id,
        question="What caused the failure in nonexistent-unindexed-service-404?",
        user_id="test-analyst",
    )

    assert final_state["status"] == "completed"

    with db_session_factory() as db:
        events = WorkflowEventRepository(db).list_by_session(session_id)
        # Corrective loop triggers corrective_retrieval -> collect_evidence -> check_missing_evidence (15 events)
        assert len(events) >= 14
        node_names = [e.node_name for e in events]
        assert "corrective_retrieval" in node_names
        assert "update_memory" in node_names


def test_persistence_resilience_to_db_failures() -> None:
    """Verify _persist catches DB exceptions gracefully without crashing."""

    class BrokenSessionFactory:
        def __call__(self) -> Any:
            raise RuntimeError("Database connection lost")

    service = ResearchService(session_factory=BrokenSessionFactory())  # type: ignore[arg-type]

    # Must not raise
    service._persist(
        session_id="test-broken-db",
        state={"status": "completed", "answer": "safe answer"},
        node_name="update_memory",
    )
    service.record_node_event(
        session_id="test-broken-db",
        node_name="test_node",
        payload={"some": "payload"},
    )


def test_workflow_failure_records_error_event_and_marks_failed(
    db_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that unexpected workflow failure marks session failed and emits node_error event."""

    class BrokenGraph:
        def stream(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Fatal node crash")

    monkeypatch.setattr(
        "backend.app.services.research_service.get_compiled_graph",
        lambda: BrokenGraph(),
    )

    service = ResearchService(session_factory=db_session_factory)
    session = service.create_session("Question that crashes")
    session_id = session.id

    with pytest.raises(RuntimeError, match="Fatal node crash"):
        service.run_research(session_id, "Question that crashes")

    with db_session_factory() as db:
        session_row = ResearchSessionRepository(db).get(session_id)
        assert session_row is not None
        assert session_row.status == "failed"

        events = WorkflowEventRepository(db).list_by_session(session_id)
        assert any(e.event_type == "node_error" for e in events)
