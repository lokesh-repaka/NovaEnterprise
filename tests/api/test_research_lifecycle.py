"""API integration tests for asynchronous research lifecycle and BackgroundTask runner (P10-3, F1, Claude.md §4.1, §12).

Tests:
- RBAC authorization: require_role(["analyst", "admin"]) for POST /api/v1/research (F1)
- 401 Unauthorized for unauthenticated requests
- 403 Forbidden for insufficient privileges (e.g. viewer role)
- 422 Validation Error when question is < 5 or > 2000 characters
- 202 Accepted for valid requests with session_id, status='running', and created_at
- BackgroundTask execution: verify research workflow runs in background to completion
- Database verification: research_sessions row and workflow_events are written
"""

from pathlib import Path

from fastapi.testclient import TestClient

from agents.rules import CANONICAL_QUESTION_TEXT
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.main import create_app
from backend.app.repositories.research import (
    ResearchSessionRepository,
    WorkflowEventRepository,
)
from backend.app.services.research_service import reset_research_service
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


def test_research_endpoint_unauthenticated_returns_401() -> None:
    """Ensure POST /api/v1/research rejects unauthenticated requests with 401."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/research",
            json={"question": "What is the Payments API architecture?"},
        )
        assert resp.status_code == 401
        assert "detail" in resp.json()


def test_research_endpoint_viewer_role_returns_403() -> None:
    """Ensure viewer role cannot launch research (requires analyst or admin)."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "viewer")
        resp = client.post(
            "/api/v1/research",
            json={"question": "What is the Payments API architecture?"},
            headers=headers,
        )
        assert resp.status_code == 403


def test_research_endpoint_validation_error_question_too_short() -> None:
    """Ensure questions under 5 characters are rejected with 422 Unprocessable Entity."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "analyst")
        resp = client.post(
            "/api/v1/research",
            json={"question": "Why?"},  # 4 chars < 5
            headers=headers,
        )
        assert resp.status_code == 422


def test_research_endpoint_validation_error_question_too_long() -> None:
    """Ensure questions over 2000 characters are rejected with 422."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "analyst")
        resp = client.post(
            "/api/v1/research",
            json={"question": "a" * 2001},
            headers=headers,
        )
        assert resp.status_code == 422


def test_research_endpoint_analyst_returns_202_and_executes_background_task() -> None:
    """Ensure POST /api/v1/research returns 202 Accepted and runs BackgroundTask to completion."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "analyst")
        payload = {
            "question": CANONICAL_QUESTION_TEXT,
            "user_id": "analyst-lead-01",
        }
        resp = client.post(
            "/api/v1/research",
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 202

        data = resp.json()
        assert "session_id" in data
        assert data["session_id"].startswith("rs-")
        assert data["status"] == "running"
        assert data["question"] == CANONICAL_QUESTION_TEXT
        assert "created_at" in data

        session_id = data["session_id"]

        # In TestClient, BackgroundTasks execute synchronously when the client context exits or yields
        # Verify research_sessions row in DB was updated by the background task
        engine = get_engine()
        factory = get_session_factory(engine)
        with factory() as db:
            session_row = ResearchSessionRepository(db).get(session_id)
            assert session_row is not None
            assert session_row.status == "completed"
            assert len(session_row.answer or "") > 0
            assert len(session_row.sub_questions) >= 1
            assert len(session_row.evidence_data) >= 1

            # Verify workflow events recorded (F16)
            events = WorkflowEventRepository(db).list_by_session(session_id)
            assert len(events) >= 12


def test_research_endpoint_admin_role_returns_202() -> None:
    """Ensure admin role can launch research workflows."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_auth_headers(client, "admin")
        resp = client.post(
            "/api/v1/research",
            json={
                "question": "What is PgBouncer connection pooling used for in Payments API?"
            },
            headers=headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "running"
        assert data["session_id"].startswith("rs-")
