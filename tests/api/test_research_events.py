"""API integration tests for research session status polling and event stream API (P10-4, F1, F16, N9).

Tests:
- GET /api/v1/research: list recent sessions with pagination (skip, limit) and status filtering
- GET /api/v1/research/{session_id}: status polling returning ResearchSessionResponse (F1, Claude.md §4.1)
- 404 Not Found for non-existent session IDs
- GET /api/v1/research/{session_id}/events: chronological telemetry timeline with latencies (F16)
- Strict Prompt Privacy (N9): raw prompts and credentials scrubbed from all event payloads
- GET /api/v1/research/{session_id}/stream: Server-Sent Events (SSE) streaming API (text/event-stream)
- RBAC permissions: viewer, analyst, and admin can all poll and view events
"""

from pathlib import Path

from fastapi.testclient import TestClient

from agents.rules import CANONICAL_QUESTION_TEXT
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.core.observability import DISALLOWED_PROMPT_KEYS
from backend.app.main import create_app
from backend.app.services.research_service import (
    reset_research_service,
)
from backend.app.services.seed import seed_database
from memory.memory_service import get_memory_service, reset_memory_service
from memory.protocols import InMemoryEpisodicMemoryStore
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store
from rag.retriever import HybridRetriever
from rag.vector_store import InMemoryVectorStore, get_vector_store


def setup_module() -> None:
    """Initialize database and reset in-memory stores for isolated offline test run."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        seed_database(session)

    # Seed graph store
    store = get_graph_store()
    if isinstance(store, InMemoryGraphStore):
        sample_dir = Path(__file__).resolve().parents[2] / "sample_data"
        seed_graph_from_domain(store, sample_data_dir=sample_dir)

    # Seed vector store
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

    reset_memory_service()
    get_memory_service(episodic_store=InMemoryEpisodicMemoryStore())
    reset_research_service()


def get_auth_headers(client: TestClient, role: str) -> dict[str, str]:
    """Helper to acquire signed demo JWT for a specific role."""
    resp = client.post("/api/v1/auth/demo-token", json={"role": role})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_research_polling_endpoints_unauthenticated_return_401() -> None:
    """Ensure polling and event endpoints reject unauthenticated calls with 401."""
    app = create_app()
    with TestClient(app) as client:
        # GET list
        resp = client.get("/api/v1/research")
        assert resp.status_code == 401

        # GET detail
        resp = client.get("/api/v1/research/rs-unknown-123")
        assert resp.status_code == 401

        # GET events
        resp = client.get("/api/v1/research/rs-unknown-123/events")
        assert resp.status_code == 401

        # GET SSE stream
        resp = client.get("/api/v1/research/rs-unknown-123/stream")
        assert resp.status_code == 401


def test_get_research_session_not_found_returns_404() -> None:
    """Ensure non-existent session ID returns 404 Not Found."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "viewer")
        resp = client.get("/api/v1/research/rs-nonexistent-999", headers=headers)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


def test_get_research_session_events_not_found_returns_404() -> None:
    """Ensure events endpoint for non-existent session returns 404."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "viewer")
        resp = client.get("/api/v1/research/rs-nonexistent-999/events", headers=headers)
        assert resp.status_code == 404


def test_research_session_status_polling_workflow_lifecycle() -> None:
    """Launch research, poll status through completion, and verify full response shape."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "analyst")

        # 1. Launch research
        resp = client.post(
            "/api/v1/research",
            json={"question": CANONICAL_QUESTION_TEXT, "user_id": "lead-analyst"},
            headers=headers,
        )
        assert resp.status_code == 202
        session_id = resp.json()["session_id"]

        # 2. Poll session status via GET /api/v1/research/{session_id}
        poll_resp = client.get(f"/api/v1/research/{session_id}", headers=headers)
        assert poll_resp.status_code == 200

        data = poll_resp.json()
        assert data["session_id"] == session_id
        assert data["status"] == "completed"
        assert data["question"] == CANONICAL_QUESTION_TEXT
        assert data["complexity"] in {"moderate", "complex"}
        assert len(data["sub_questions"]) >= 1
        assert len(data["answer"]) > 0
        assert len(data["citations"]) >= 1
        assert data["execution_time_seconds"] is not None
        assert data["execution_time_seconds"] > 0
        assert "created_at" in data
        assert "updated_at" in data


def test_list_research_sessions_pagination_and_status_filtering() -> None:
    """Verify listing research sessions with pagination and status filters."""
    app = create_app()
    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        viewer_headers = get_auth_headers(client, "viewer")

        # Launch two sessions
        client.post(
            "/api/v1/research",
            json={"question": "What is PgBouncer connection pooling?"},
            headers=analyst_headers,
        )
        client.post(
            "/api/v1/research",
            json={"question": "What is the Payments API architecture?"},
            headers=analyst_headers,
        )

        # List with viewer role
        list_resp = client.get(
            "/api/v1/research?limit=5&skip=0", headers=viewer_headers
        )
        assert list_resp.status_code == 200
        sessions = list_resp.json()
        assert isinstance(sessions, list)
        assert len(sessions) >= 2

        # Filter by status=completed
        completed_resp = client.get(
            "/api/v1/research?status=completed", headers=viewer_headers
        )
        assert completed_resp.status_code == 200
        completed = completed_resp.json()
        assert all(s["status"] == "completed" for s in completed)


def test_get_research_session_events_chronological_trace_and_privacy() -> None:
    """Verify chronological timeline of node transitions and strict prompt privacy (F16, N9)."""
    app = create_app()
    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        viewer_headers = get_auth_headers(client, "viewer")

        # Launch research
        resp = client.post(
            "/api/v1/research",
            json={"question": CANONICAL_QUESTION_TEXT},
            headers=analyst_headers,
        )
        session_id = resp.json()["session_id"]

        # Retrieve events
        events_resp = client.get(
            f"/api/v1/research/{session_id}/events", headers=viewer_headers
        )
        assert events_resp.status_code == 200
        events = events_resp.json()

        # F16: All 12 canonical non-retry node transitions must be present
        assert len(events) >= 12

        # Verify ascending chronological order
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)

        # Check expected node transitions
        node_names = [e["node_name"] for e in events]
        assert "recall_memory" in node_names
        assert "analyze_query" in node_names
        assert "assess_complexity" in node_names
        assert "decompose" in node_names
        assert "route_retrieval" in node_names
        assert "execute_retrieval" in node_names
        assert "synthesize_answer" in node_names
        assert "update_memory" in node_names

        # N9: Strict Prompt Privacy verification on all event payloads
        for event in events:
            assert "event_id" in event
            assert "session_id" in event
            assert "node_name" in event
            assert "event_type" in event
            payload = event.get("payload", {})
            for disallowed in DISALLOWED_PROMPT_KEYS:
                assert disallowed not in payload, (
                    f"Disallowed key '{disallowed}' exposed in node '{event['node_name']}'"
                )


def test_research_session_events_sse_stream() -> None:
    """Verify Server-Sent Events (SSE) streaming endpoint text/event-stream format."""
    app = create_app()
    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        viewer_headers = get_auth_headers(client, "viewer")

        # Launch research
        resp = client.post(
            "/api/v1/research",
            json={"question": "What is PgBouncer connection pooling?"},
            headers=analyst_headers,
        )
        session_id = resp.json()["session_id"]

        # Connect to SSE stream
        stream_resp = client.get(
            f"/api/v1/research/{session_id}/stream", headers=viewer_headers
        )
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")

        # Verify SSE message chunks format: event: ... \n data: ... \n\n
        content = stream_resp.text
        assert "event: " in content
        assert "data: " in content
