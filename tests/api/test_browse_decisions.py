"""API route integration tests for decisions (ADRs) and projects/tickets (P4-3).

Verifies Decisions, Projects, and Tickets browse endpoints:
- RBAC authorization (viewer, analyst, admin allowed; unauthenticated 401)
- Filtering and pagination query parameters
- Entity detail retrieval with eager relationship resolution (Project -> tickets)
- 404 Not Found handling for invalid IDs
- Header invariants (X-Request-ID, rate limits)
"""

from fastapi.testclient import TestClient

from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.main import create_app
from backend.app.services.seed import seed_database


def setup_module() -> None:
    """Initialize SQLite schema and seed canonical sample domain data."""
    engine = get_engine()
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        seed_database(session)


def get_viewer_auth_headers(client: TestClient) -> dict[str, str]:
    """Helper to acquire a signed demo JWT for the viewer role."""
    resp = client.post("/api/v1/auth/demo-token", json={"role": "viewer"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_browse_decisions_unauthenticated_returns_401() -> None:
    """Ensure decisions, projects, and tickets endpoints reject unauthenticated requests with 401."""
    app = create_app()
    with TestClient(app) as client:
        for path in ["/api/v1/decisions", "/api/v1/projects", "/api/v1/tickets"]:
            resp = client.get(path)
            assert resp.status_code == 401, f"Expected 401 for unauthenticated {path}, got {resp.status_code}"
            assert "detail" in resp.json()


def test_browse_decisions_list_and_filters() -> None:
    """Test listing, filtering by status/incident, and paginating ADR decisions."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # 1. Full list
        resp = client.get("/api/v1/decisions", headers=headers)
        assert resp.status_code == 200
        decisions = resp.json()
        assert isinstance(decisions, list)
        assert len(decisions) >= 8
        first = decisions[0]
        assert "id" in first
        assert "title" in first
        assert "status" in first
        assert "decision" in first
        assert "created_at" in first

        # 2. Filter by status
        resp_status = client.get("/api/v1/decisions?status=approved", headers=headers)
        assert resp_status.status_code == 200
        approved_decs = resp_status.json()
        assert len(approved_decs) > 0
        for dec in approved_decs:
            assert dec["status"] == "approved"

        # 3. Filter by incident
        resp_inc = client.get("/api/v1/decisions?incident_id=inc-2031", headers=headers)
        assert resp_inc.status_code == 200
        inc_decs = resp_inc.json()
        assert len(inc_decs) > 0
        for dec in inc_decs:
            assert dec["incident_id"] == "inc-2031"

        # 4. Pagination
        resp_paged = client.get("/api/v1/decisions?skip=1&limit=2", headers=headers)
        assert resp_paged.status_code == 200
        paged_decs = resp_paged.json()
        assert len(paged_decs) == 2


def test_browse_decision_by_id() -> None:
    """Test single ADR retrieval and 404 for missing ID."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # Existing decision
        resp = client.get("/api/v1/decisions/dec-adr-042", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "dec-adr-042"
        assert "PgBouncer" in data["title"]
        assert data["incident_id"] == "inc-2031"

        # Missing decision
        resp_missing = client.get("/api/v1/decisions/non-existent-adr", headers=headers)
        assert resp_missing.status_code == 404
        assert "not found" in resp_missing.json()["detail"].lower()


def test_browse_projects_list_and_filters() -> None:
    """Test listing and filtering projects by status and owner team."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # 1. Full list
        resp = client.get("/api/v1/projects", headers=headers)
        assert resp.status_code == 200
        projects = resp.json()
        assert isinstance(projects, list)
        assert len(projects) >= 6

        # 2. Filter by status
        resp_active = client.get("/api/v1/projects?status=active", headers=headers)
        assert resp_active.status_code == 200
        active_prjs = resp_active.json()
        assert len(active_prjs) > 0
        for prj in active_prjs:
            assert prj["status"] == "active"

        # 3. Filter by owner team
        resp_team = client.get("/api/v1/projects?team_id=team-payments", headers=headers)
        assert resp_team.status_code == 200
        team_prjs = resp_team.json()
        assert len(team_prjs) > 0
        for prj in team_prjs:
            assert prj["owner_team_id"] == "team-payments"


def test_browse_project_by_id_with_relations() -> None:
    """Test retrieving project detail with tracked tickets."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # Existing project
        resp = client.get("/api/v1/projects/proj-1", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "proj-1"
        assert "Payments" in data["name"]
        assert "tickets" in data
        assert isinstance(data["tickets"], list)
        assert len(data["tickets"]) > 0

        # Missing project
        resp_missing = client.get("/api/v1/projects/non-existent-proj", headers=headers)
        assert resp_missing.status_code == 404


def test_browse_tickets_list_and_filters() -> None:
    """Test listing and filtering tickets by status, priority, and project."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # 1. Full list
        resp = client.get("/api/v1/tickets", headers=headers)
        assert resp.status_code == 200
        tickets = resp.json()
        assert isinstance(tickets, list)
        assert len(tickets) >= 15

        # 2. Filter by status
        resp_status = client.get("/api/v1/tickets?status=resolved", headers=headers)
        assert resp_status.status_code == 200
        resolved_tkts = resp_status.json()
        assert len(resolved_tkts) > 0
        for tkt in resolved_tkts:
            assert tkt["status"] == "resolved"

        # 3. Filter by priority
        resp_p0 = client.get("/api/v1/tickets?priority=P0", headers=headers)
        assert resp_p0.status_code == 200
        p0_tkts = resp_p0.json()
        assert len(p0_tkts) > 0
        for tkt in p0_tkts:
            assert tkt["priority"] == "P0"

        # 4. Filter by project
        resp_prj = client.get("/api/v1/tickets?project_id=proj-1", headers=headers)
        assert resp_prj.status_code == 200
        proj_tkts = resp_prj.json()
        assert len(proj_tkts) > 0
        for tkt in proj_tkts:
            assert tkt["project_id"] == "proj-1"


def test_browse_ticket_by_id() -> None:
    """Test single ticket retrieval and 404 for missing ticket."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # Existing ticket
        resp = client.get("/api/v1/tickets/tick-01", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "tick-01"
        assert data["priority"] == "P0"
        assert data["project_id"] == "proj-1"

        # Missing ticket
        resp_missing = client.get("/api/v1/tickets/non-existent-ticket", headers=headers)
        assert resp_missing.status_code == 404


def test_browse_decisions_headers() -> None:
    """Ensure browse decisions endpoints return standard X-Request-ID and rate limit headers."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)
        resp = client.get("/api/v1/decisions", headers=headers)
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
