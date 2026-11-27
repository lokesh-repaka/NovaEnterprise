"""Unit tests for LangGraph StateGraph wiring, 13 nodes, and conditional edges (P10-1, F1–F12, Claude.md §7.3, docs/LLD.md §5).

Validates:
- 13-node topology exposed in GRAPH_NODES:
  1. recall_memory
  2. analyze_query
  3. assess_complexity
  4. decompose
  5. route_retrieval
  6. execute_retrieval
  7. collect_evidence
  8. check_missing_evidence
  9. corrective_retrieval
  10. verify_evidence
  11. synthesize_answer
  12. verify_citations
  13. update_memory
- Authoritative test: test_graph_shape_matches_frontend_assumptions (F5)
- Edge connections exposed in GRAPH_EDGES
- Conditional edge routing logic after check_missing_evidence:
  - If needs_retry is True -> routes to corrective_retrieval
  - If needs_retry is False -> routes to verify_evidence
- End-to-end graph compilation and execution via build_graph().invoke():
  - Canonical question produces cited Markdown answer, resolved citations, and completed status
  - Bounded corrective loop terminates within MAX_CORRECTIVE_ROUNDS=1
  - Memory persistence verifies completed interaction in episodic store
"""

from pathlib import Path
from typing import Any

import pytest

from agents.graph import (
    GRAPH_EDGES,
    GRAPH_NODES,
    build_graph,
    get_compiled_graph,
    route_after_check_missing,
)
from agents.nodes.recall_memory import recall_memory, recall_memory_node
from agents.rules import CANONICAL_QUESTION_TEXT
from agents.state import ResearchState
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.services.seed import seed_database
from memory.memory_service import get_memory_service, reset_memory_service
from memory.protocols import InMemoryEpisodicMemoryStore
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store
from rag.retriever import HybridRetriever
from rag.vector_store import InMemoryVectorStore, get_vector_store


@pytest.fixture(autouse=True)
def setup_test_environment() -> Any:
    """Initialize in-memory relational, graph, vector, and episodic stores for offline execution."""
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
# Graph Shape & Topology Tests
# =============================================================================


def test_graph_shape_matches_frontend_assumptions() -> None:
    """Authoritative F5 test: Guards the exact 13-node topology and edge structure rendered by UI."""
    assert len(GRAPH_NODES) == 13

    expected_nodes = [
        "recall_memory",
        "analyze_query",
        "assess_complexity",
        "decompose",
        "route_retrieval",
        "execute_retrieval",
        "collect_evidence",
        "check_missing_evidence",
        "corrective_retrieval",
        "verify_evidence",
        "synthesize_answer",
        "verify_citations",
        "update_memory",
    ]
    assert GRAPH_NODES == expected_nodes

    # Verify key sequential transitions are present in GRAPH_EDGES
    assert ("recall_memory", "analyze_query") in GRAPH_EDGES
    assert ("analyze_query", "assess_complexity") in GRAPH_EDGES
    assert ("assess_complexity", "decompose") in GRAPH_EDGES
    assert ("decompose", "route_retrieval") in GRAPH_EDGES
    assert ("route_retrieval", "execute_retrieval") in GRAPH_EDGES
    assert ("execute_retrieval", "collect_evidence") in GRAPH_EDGES
    assert ("collect_evidence", "check_missing_evidence") in GRAPH_EDGES
    assert ("corrective_retrieval", "collect_evidence") in GRAPH_EDGES
    assert ("verify_evidence", "synthesize_answer") in GRAPH_EDGES
    assert ("synthesize_answer", "verify_citations") in GRAPH_EDGES
    assert ("verify_citations", "update_memory") in GRAPH_EDGES


def test_conditional_edge_routing_logic() -> None:
    """Test conditional router after check_missing_evidence directs to corrective or verification."""
    # 1. When needs_retry is True -> routes to corrective_retrieval
    state_retry = ResearchState(
        session_id="test-retry",
        question="Query needing retry",
        needs_retry=True,
    )
    assert route_after_check_missing(state_retry) == "corrective_retrieval"
    assert route_after_check_missing({"needs_retry": True}) == "corrective_retrieval"

    # 2. When needs_retry is False -> routes to verify_evidence
    state_complete = ResearchState(
        session_id="test-ok",
        question="Query all backed",
        needs_retry=False,
    )
    assert route_after_check_missing(state_complete) == "verify_evidence"
    assert route_after_check_missing({"needs_retry": False}) == "verify_evidence"


# =============================================================================
# recall_memory Node Tests
# =============================================================================


def test_recall_memory_node_executes() -> None:
    """Test recall_memory node extracts session context and populates metadata."""
    state = ResearchState(
        session_id="test-recall-sess",
        question="What is the architecture?",
        user_id="analyst-lead",
    )
    result = recall_memory(state)
    assert result["current_node"] == "recall_memory"
    assert result["metadata"]["memory_recalled"] is True
    assert recall_memory_node is recall_memory


# =============================================================================
# Graph Compilation and Execution Tests
# =============================================================================


def test_build_graph_compiles() -> None:
    """Test build_graph compiles cleanly into a Runnable StateGraph."""
    graph = build_graph()
    assert graph is not None
    assert hasattr(graph, "invoke")
    assert get_compiled_graph() is not None


def test_end_to_end_graph_execution_canonical_question() -> None:
    """Execute complete compiled StateGraph on CANONICAL_QUESTION_TEXT through all nodes."""
    graph = build_graph()

    input_payload = {
        "session_id": "test-graph-e2e-canonical",
        "question": CANONICAL_QUESTION_TEXT,
        "user_id": "lead-analyst",
    }

    final_state = graph.invoke(input_payload)

    # State schema assertions
    assert final_state["status"] == "completed"
    assert final_state["session_id"] == "test-graph-e2e-canonical"
    assert final_state["complexity"] in {"moderate", "complex"}

    # Sub-questions and evidence assertions
    assert len(final_state["sub_questions"]) >= 1
    assert len(final_state["evidence"]) >= 1

    # Answer synthesis and citation assertions
    assert len(final_state["answer"]) > 0
    assert len(final_state["citations"]) > 0
    assert final_state["citations_verified"] is True

    # Memory update verification
    mem_service = get_memory_service()
    entries = mem_service.get_episodic_history("test-graph-e2e-canonical")
    assert len(entries) >= 1
    assert entries[0].user_id == "lead-analyst"


def test_end_to_end_graph_execution_simple_question() -> None:
    """Execute complete compiled StateGraph on a simple factual question."""
    graph = build_graph()

    input_payload = {
        "session_id": "test-graph-simple-q",
        "question": "What is PgBouncer connection pooling used for in Payments API?",
        "user_id": "test-analyst",
    }

    final_state = graph.invoke(input_payload)

    assert final_state["status"] == "completed"
    assert final_state["session_id"] == "test-graph-simple-q"
    assert len(final_state["answer"]) > 0
    assert "citations_verified" in final_state


def test_bounded_corrective_loop_execution() -> None:
    """Verify that StateGraph bounded corrective loop terminates within MAX_CORRECTIVE_ROUNDS=1."""
    graph = build_graph()

    # Query with non-existent system to trigger missing evidence and corrective reformulation
    input_payload = {
        "session_id": "test-graph-corrective-loop",
        "question": "What caused the outage in nonexistent-quantum-service-xyz?",
        "user_id": "test-analyst",
    }

    final_state = graph.invoke(input_payload)

    # Graph must terminate successfully and corrective_rounds must be bounded at <= 1
    assert final_state["status"] == "completed"
    assert final_state.get("corrective_rounds", 0) <= 1
    assert final_state.get("needs_retry") is False


def test_graph_with_checkpointer_integration() -> None:
    """Verify build_graph accepts and functions with a LangGraph MemorySaver checkpointer."""
    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    assert graph is not None

    input_payload = {
        "session_id": "test-checkpointer-sess",
        "question": "What is PgBouncer?",
        "user_id": "test-analyst",
    }
    config = {"configurable": {"thread_id": "thread-1"}}
    final_state = graph.invoke(input_payload, config=config)
    assert final_state["status"] == "completed"


def test_recall_memory_telemetry_resilience(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify recall_memory handles tracer exceptions without raising."""
    from backend.app.core.observability import ObservabilityTracer

    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Tracer unavailable")

    monkeypatch.setattr(ObservabilityTracer, "node", _raise)

    state = ResearchState(
        session_id="test-telemetry-resilience",
        question="What is the architecture?",
        user_id="analyst-lead",
    )
    result = recall_memory(state)
    assert result["current_node"] == "recall_memory"
    assert result["metadata"]["memory_recalled"] is True
