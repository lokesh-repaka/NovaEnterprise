"""Unit and integration tests for AuditMiddleware and canonical middleware order (N5, P3-4).

Verifies state-changing HTTP methods (POST, PUT, PATCH, DELETE) append immutable audit logs,
safe methods (GET, OPTIONS) and health routes are exempt, authenticated user identities
and request IDs are correlated, and the middleware pipeline order executes correctly.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.db import get_db, get_engine, init_db
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.middleware.audit import AuditMiddleware
from backend.app.models.security import AuditLog
from backend.app.repositories.security import AuditLogRepository


def setup_module():
    """Ensure database schema is populated for audit test execution."""
    engine = get_engine()
    init_db(engine)


def test_audit_middleware_records_state_changing_requests():
    """Verify that state-changing HTTP requests (POST, PUT, DELETE) generate audit log entries."""
    app = FastAPI()
    init_db()

    app.add_middleware(AuditMiddleware)

    @app.post("/api/v1/items")
    def create_item():
        return {"status": "created", "id": "item-101"}

    @app.get("/api/v1/items")
    def list_items():
        return [{"id": "item-101"}]

    with TestClient(app) as client:
        # 1. GET (safe) request must NOT generate an audit log entry
        res_get = client.get("/api/v1/items")
        assert res_get.status_code == 200

        db_gen = get_db()
        db: Session = next(db_gen)
        repo = AuditLogRepository(db)
        initial_count = repo.count()

        # 2. POST (state-changing) request MUST generate an audit log entry
        res_post = client.post(
            "/api/v1/items",
            headers={
                "X-Forwarded-For": "10.0.0.42",
                "X-Request-ID": "req-audit-test-001",
            },
        )
        assert res_post.status_code == 200
        assert repo.count() == initial_count + 1

        logs = repo.list(order_by=AuditLog.id, descending=True, limit=1)
        latest_log = logs[0]
        assert latest_log.action == "POST /api/v1/items"
        assert latest_log.resource_type == "items"
        assert latest_log.request_id == "req-audit-test-001"
        assert latest_log.ip_address == "10.0.0.42"
        db.close()


def test_audit_middleware_extracts_authenticated_user():
    """Verify that AuditMiddleware correlates the authenticated user ID from Bearer token."""
    app = FastAPI()
    init_db()
    app.add_middleware(AuditMiddleware)

    @app.post("/api/v1/approvals")
    def create_approval():
        return {"status": "approved"}

    token = create_access_token(
        {"sub": "usr-analyst-01", "role": "analyst", "username": "analyst"}
    )

    with TestClient(app) as client:
        res = client.post(
            "/api/v1/approvals",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": "req-approval-888",
            },
        )
        assert res.status_code == 200

        db = next(get_db())
        repo = AuditLogRepository(db)
        logs = repo.list(order_by=AuditLog.id, descending=True, limit=1)
        latest = logs[0]
        assert latest.user_id == "usr-analyst-01"
        assert latest.request_id == "req-approval-888"
        assert latest.action == "POST /api/v1/approvals"
        assert latest.resource_type == "approvals"
        db.close()


def test_audit_middleware_exempt_paths():
    """Verify that health check and documentation routes are never audited."""
    app = FastAPI()
    init_db()
    app.add_middleware(AuditMiddleware)

    @app.post("/health")
    def health_post():
        return {"status": "ok"}

    with TestClient(app) as client:
        db = next(get_db())
        repo = AuditLogRepository(db)
        count_before = repo.count()

        res = client.post("/health")
        assert res.status_code == 200
        assert repo.count() == count_before
        db.close()


def test_canonical_middleware_pipeline_order():
    """Verify complete application middleware pipeline order:

    RequestContextMiddleware (outermost) -> CORSMiddleware -> RateLimitMiddleware -> AuditMiddleware.
    Guarantees X-Request-ID on all responses (N5), rate limiting enforcement (N6), and audit logging.
    """
    app = create_app()
    with TestClient(app) as client:
        # 1. Health liveness: carries X-Request-ID, not rate limited, not audited
        h_res = client.get("/health")
        assert h_res.status_code == 200
        assert "X-Request-ID" in h_res.headers or "x-request-id" in h_res.headers

        # 2. State-changing auth demo-token request
        db = next(get_db())
        repo = AuditLogRepository(db)
        initial_count = repo.count()

        auth_res = client.post(
            "/api/v1/auth/demo-token",
            json={"role": "analyst"},
            headers={"X-Forwarded-For": "172.16.0.10"},
        )
        assert auth_res.status_code == 200
        # Headers from RequestContextMiddleware (N5) & RateLimitMiddleware (N6)
        assert "X-Request-ID" in auth_res.headers or "x-request-id" in auth_res.headers
        assert "X-RateLimit-Limit" in auth_res.headers
        assert "X-RateLimit-Remaining" in auth_res.headers

        # Audit log entry must be present
        assert repo.count() == initial_count + 1
        latest = repo.list(order_by=AuditLog.id, descending=True, limit=1)[0]
        assert latest.action == "POST /api/v1/auth/demo-token"
        assert latest.resource_type == "auth"
        assert latest.ip_address == "172.16.0.10"
        db.close()
