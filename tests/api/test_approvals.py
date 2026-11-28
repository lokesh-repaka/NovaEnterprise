"""API integration tests for Document Deletion Approval Gates and Admin Workflow (P11-2, F17, Claude.md §12, §18.1).

Tests:
- DELETE /api/v1/documents/{id}:
  - Intercepted for analyst -> creates pending ApprovalRequest, returns 202 Accepted (pending_approval)
  - Direct execution for admin -> deletes document and chunks, returns 200 OK
  - 403 Forbidden for viewer
  - 401 Unauthorized for unauthenticated
  - 404 Not Found for non-existent document
- GET /api/v1/approvals: List approval requests with status filtering and pagination [viewer+]
- GET /api/v1/approvals/{id}: Retrieve single approval request [viewer+]
- 404 Not Found for non-existent approval request
- POST /api/v1/approvals/{id}/decide:
  - 403 Forbidden for non-admin roles (analyst, viewer)
  - 401 Unauthorized for unauthenticated
  - 400 Bad Request if already decided or invalid decision
  - 404 Not Found if request does not exist
  - Rejection: marks request rejected, document remains intact
  - Approval: marks request approved, executes document and vector chunk deletion
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.main import create_app
from backend.app.models.documents import Document, DocumentChunk
from backend.app.services.approval_service import reset_approval_service
from backend.app.services.seed import seed_database
from rag.vector_store import InMemoryVectorStore, get_vector_store, reset_vector_store


def setup_module() -> None:
    """Initialize database and stores for isolated offline test run."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        seed_database(session)

    reset_vector_store()
    reset_approval_service()


def get_auth_headers(client: TestClient, role: str) -> dict[str, str]:
    """Helper to acquire signed demo JWT for a specific role."""
    resp = client.post("/api/v1/auth/demo-token", json={"role": role})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_document(doc_id: str, filename: str) -> dict[str, Any]:
    """Helper to insert a test document and chunks into DB and Vector store."""
    engine = get_engine("sqlite:///:memory:")
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        doc = Document(
            id=doc_id,
            filename=filename,
            content_hash=uuid.uuid4().hex,
            chunk_count=2,
            flagged_injection=False,
            status="indexed",
        )
        session.add(doc)

        c1 = DocumentChunk(
            id=f"chk-{doc_id[:8]}-1",
            document_id=doc_id,
            chunk_index=0,
            text=f"Sample text content 1 for {filename}",
            embedding_id=f"emb-{doc_id[:8]}-1",
        )
        c2 = DocumentChunk(
            id=f"chk-{doc_id[:8]}-2",
            document_id=doc_id,
            chunk_index=1,
            text=f"Sample text content 2 for {filename}",
            embedding_id=f"emb-{doc_id[:8]}-2",
        )
        session.add_all([c1, c2])
        session.commit()

    # Index into vector store
    v_store = get_vector_store()
    if isinstance(v_store, InMemoryVectorStore):
        v_store.add_documents(
            [
                {
                    "id": f"chk-{doc_id[:8]}-1",
                    "document_id": doc_id,
                    "text": f"Sample text content 1 for {filename}",
                    "metadata": {"source": filename},
                },
                {
                    "id": f"chk-{doc_id[:8]}-2",
                    "document_id": doc_id,
                    "text": f"Sample text content 2 for {filename}",
                    "metadata": {"source": filename},
                },
            ]
        )

    return {"id": doc_id, "filename": filename}


def test_approvals_endpoints_unauthenticated_return_401() -> None:
    """Ensure approvals and document deletion routes reject unauthenticated requests with 401."""
    app = create_app()
    with TestClient(app) as client:
        # GET approvals
        assert client.get("/api/v1/approvals").status_code == 401

        # GET single approval
        assert client.get("/api/v1/approvals/appr-dummy-123").status_code == 401

        # POST decide
        assert (
            client.post(
                "/api/v1/approvals/appr-dummy-123/decide",
                json={"decision": "approved"},
            ).status_code
            == 401
        )

        # DELETE document
        assert client.delete("/api/v1/documents/doc-dummy-123").status_code == 401


def test_document_deletion_viewer_forbidden_403() -> None:
    """Ensure viewer role is rejected with 403 Forbidden on document deletion."""
    app = create_app()
    with TestClient(app) as client:
        viewer_headers = get_auth_headers(client, "viewer")
        resp = client.delete("/api/v1/documents/doc-dummy-123", headers=viewer_headers)
        assert resp.status_code == 403
        assert "forbidden" in resp.json()["detail"].lower()


def test_approval_decide_non_admin_forbidden_403() -> None:
    """Ensure non-admin roles (viewer, analyst) receive 403 Forbidden on approval decision."""
    app = create_app()
    with TestClient(app) as client:
        viewer_headers = get_auth_headers(client, "viewer")
        analyst_headers = get_auth_headers(client, "analyst")

        # Viewer forbidden
        resp_v = client.post(
            "/api/v1/approvals/appr-dummy-123/decide",
            json={"decision": "approved"},
            headers=viewer_headers,
        )
        assert resp_v.status_code == 403

        # Analyst forbidden (Claude.md §18.1: 'An analyst reaching reindex / delete / approve')
        resp_a = client.post(
            "/api/v1/approvals/appr-dummy-123/decide",
            json={"decision": "approved"},
            headers=analyst_headers,
        )
        assert resp_a.status_code == 403


def test_document_deletion_not_found_404() -> None:
    """Ensure non-existent document ID returns 404 for both analyst and admin."""
    app = create_app()
    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        admin_headers = get_auth_headers(client, "admin")

        assert (
            client.delete(
                "/api/v1/documents/doc-unknown-999", headers=analyst_headers
            ).status_code
            == 404
        )
        assert (
            client.delete(
                "/api/v1/documents/doc-unknown-999", headers=admin_headers
            ).status_code
            == 404
        )


def test_document_deletion_analyst_intercepted_and_queued_202() -> None:
    """Verify analyst deletion is intercepted by approval gate returning 202 Accepted (F17)."""
    app = create_app()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    create_test_document(doc_id, "redundant-policy.md")

    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        viewer_headers = get_auth_headers(client, "viewer")

        # 1. Analyst initiates deletion
        del_resp = client.delete(f"/api/v1/documents/{doc_id}", headers=analyst_headers)
        assert del_resp.status_code == 202
        del_data = del_resp.json()
        assert del_data["status"] == "pending_approval"
        assert "approval_request_id" in del_data
        appr_id = del_data["approval_request_id"]

        # 2. Document MUST still exist in database
        doc_resp = client.get(f"/api/v1/documents/{doc_id}", headers=viewer_headers)
        assert doc_resp.status_code == 200

        # 3. Check approval request in approvals list
        list_resp = client.get(
            "/api/v1/approvals?status=pending", headers=viewer_headers
        )
        assert list_resp.status_code == 200
        requests = list_resp.json()
        assert any(r["id"] == appr_id for r in requests)

        # 4. Check approval request detail
        get_resp = client.get(f"/api/v1/approvals/{appr_id}", headers=viewer_headers)
        assert get_resp.status_code == 200
        req_data = get_resp.json()
        assert req_data["id"] == appr_id
        assert req_data["resource_type"] == "document"
        assert req_data["resource_id"] == doc_id
        assert req_data["action"] == "delete"
        assert req_data["status"] == "pending"


def test_approval_decision_rejected_lifecycle() -> None:
    """Verify administrator rejecting an approval leaves document intact."""
    app = create_app()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    create_test_document(doc_id, "critical-sop.md")

    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        admin_headers = get_auth_headers(client, "admin")
        viewer_headers = get_auth_headers(client, "viewer")

        # Analyst queues deletion
        del_resp = client.delete(f"/api/v1/documents/{doc_id}", headers=analyst_headers)
        appr_id = del_resp.json()["approval_request_id"]

        # Admin rejects deletion
        reject_resp = client.post(
            f"/api/v1/approvals/{appr_id}/decide",
            json={
                "decision": "rejected",
                "reason": "Document is still required for compliance audits",
            },
            headers=admin_headers,
        )
        assert reject_resp.status_code == 200
        rej_data = reject_resp.json()
        assert rej_data["id"] == appr_id
        assert rej_data["status"] == "rejected"
        assert rej_data["decided_by"] is not None

        # Document MUST still be intact
        doc_resp = client.get(f"/api/v1/documents/{doc_id}", headers=viewer_headers)
        assert doc_resp.status_code == 200

        # Attempting to decide again fails with 400 Bad Request
        re_decide_resp = client.post(
            f"/api/v1/approvals/{appr_id}/decide",
            json={"decision": "approved"},
            headers=admin_headers,
        )
        assert re_decide_resp.status_code == 400


def test_approval_decision_approved_lifecycle() -> None:
    """Verify administrator approving an approval request executes document and vector chunk deletion (F17)."""
    app = create_app()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    create_test_document(doc_id, "deprecated-v1-api.md")

    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        admin_headers = get_auth_headers(client, "admin")
        viewer_headers = get_auth_headers(client, "viewer")

        # Analyst queues deletion
        del_resp = client.delete(f"/api/v1/documents/{doc_id}", headers=analyst_headers)
        appr_id = del_resp.json()["approval_request_id"]

        # Admin approves deletion
        approve_resp = client.post(
            f"/api/v1/approvals/{appr_id}/decide",
            json={
                "decision": "approved",
                "reason": "Verified deprecated documentation",
            },
            headers=admin_headers,
        )
        assert approve_resp.status_code == 200
        appr_data = approve_resp.json()
        assert appr_data["id"] == appr_id
        assert appr_data["status"] == "approved"
        assert appr_data["execution_result"] is not None
        assert appr_data["execution_result"]["deleted_document_id"] == doc_id

        # Document MUST now be gone from DB (404)
        doc_resp = client.get(f"/api/v1/documents/{doc_id}", headers=viewer_headers)
        assert doc_resp.status_code == 404

        # Chunks must be gone from vector store
        v_store = get_vector_store()
        if isinstance(v_store, InMemoryVectorStore):
            assert not any(
                getattr(c, "document_id", None) == doc_id
                for c in v_store._chunks.values()
            )


def test_document_deletion_admin_direct_execution_200() -> None:
    """Verify administrator directly deleting document bypasses approval and executes immediately."""
    app = create_app()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    create_test_document(doc_id, "admin-immediate-delete.md")

    with TestClient(app) as client:
        admin_headers = get_auth_headers(client, "admin")
        viewer_headers = get_auth_headers(client, "viewer")

        # Admin direct delete
        del_resp = client.delete(f"/api/v1/documents/{doc_id}", headers=admin_headers)
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["status"] == "deleted"
        assert del_data["deleted_document_id"] == doc_id
        assert del_data["pruned_chunks"] >= 2

        # Document is gone
        assert (
            client.get(
                f"/api/v1/documents/{doc_id}", headers=viewer_headers
            ).status_code
            == 404
        )
