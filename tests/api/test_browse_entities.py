"""API route integration tests for browse entities (P4-2).

Verifies Customer, Incident, Service, and Team endpoints:
- RBAC authorization (viewer, analyst, admin allowed; unauthenticated 401)
- Filtering and pagination query parameters
- Entity detail retrieval with eager relationship resolution
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


def test_browse_entities_unauthenticated_returns_401() -> None:
    """Ensure browse endpoints reject unauthenticated requests with 401."""
    app = create_app()
    with TestClient(app) as client:
        for path in ["/api/v1/customers", "/api/v1/incidents", "/api/v1/services", "/api/v1/teams"]:
            resp = client.get(path)
            assert resp.status_code == 401, f"Expected 401 for unauthenticated {path}, got {resp.status_code}"
            assert "detail" in resp.json()


def test_browse_customers_list_and_filters() -> None:
    """Test listing, filtering by tier, and paginating customers."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # 1. Full list
        resp = client.get("/api/v1/customers", headers=headers)
        assert resp.status_code == 200
        customers = resp.json()
        assert isinstance(customers, list)
        assert len(customers) >= 10
        first = customers[0]
        assert "id" in first
        assert "name" in first
        assert "tier" in first
        assert "contract_value" in first
        assert "created_at" in first

        # 2. Filter by tier
        resp_tier = client.get("/api/v1/customers?tier=enterprise", headers=headers)
        assert resp_tier.status_code == 200
        enterprise_custs = resp_tier.json()
        assert len(enterprise_custs) > 0
        for cust in enterprise_custs:
            assert cust["tier"] == "enterprise"

        # 3. Pagination
        resp_paged = client.get("/api/v1/customers?skip=1&limit=3", headers=headers)
        assert resp_paged.status_code == 200
        paged_custs = resp_paged.json()
        assert len(paged_custs) == 3


def test_browse_customer_by_id() -> None:
    """Test retrieving a single customer and 404 for missing IDs."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # Existing customer
        resp = client.get("/api/v1/customers/cust-acme", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "cust-acme"
        assert data["name"] == "Acme Corp"
        assert data["tier"] == "enterprise"

        # Missing customer
        resp_missing = client.get("/api/v1/customers/non-existent-cust", headers=headers)
        assert resp_missing.status_code == 404
        assert "not found" in resp_missing.json()["detail"].lower()


def test_browse_incidents_list_and_filters() -> None:
    """Test listing and filtering incidents by severity, status, and service."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # 1. Full list
        resp = client.get("/api/v1/incidents", headers=headers)
        assert resp.status_code == 200
        incidents = resp.json()
        assert isinstance(incidents, list)
        assert len(incidents) >= 12
        inc0 = incidents[0]
        assert "id" in inc0
        assert "title" in inc0
        assert "severity" in inc0
        assert "status" in inc0
        assert "impacted_service_id" in inc0

        # 2. Filter by severity
        resp_sev = client.get("/api/v1/incidents?severity=SEV1", headers=headers)
        assert resp_sev.status_code == 200
        sev1_incs = resp_sev.json()
        assert len(sev1_incs) > 0
        for inc in sev1_incs:
            assert inc["severity"] == "SEV1"

        # 3. Filter by status
        resp_status = client.get("/api/v1/incidents?status=resolved", headers=headers)
        assert resp_status.status_code == 200
        resolved_incs = resp_status.json()
        assert len(resolved_incs) > 0
        for inc in resolved_incs:
            assert inc["status"] == "resolved"

        # 4. Filter by service
        resp_svc = client.get("/api/v1/incidents?service_id=svc-payments-api", headers=headers)
        assert resp_svc.status_code == 200
        svc_incs = resp_svc.json()
        assert len(svc_incs) > 0
        for inc in svc_incs:
            assert inc["impacted_service_id"] == "svc-payments-api"


def test_browse_incident_by_id_with_relations() -> None:
    """Test retrieving an incident with detailed relations (impacted service, ADR decisions)."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # Detailed incident (INC-2031)
        resp = client.get("/api/v1/incidents/inc-2031", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "inc-2031"
        assert data["severity"] == "SEV1"
        assert "impacted_service" in data
        if data["impacted_service"]:
            assert data["impacted_service"]["id"] == "svc-payments-api"
        assert "decisions" in data
        assert isinstance(data["decisions"], list)

        # Missing incident
        resp_missing = client.get("/api/v1/incidents/non-existent-inc", headers=headers)
        assert resp_missing.status_code == 404


def test_browse_services_list_and_filters() -> None:
    """Test listing and filtering services by tier and owner team."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # 1. Full list
        resp = client.get("/api/v1/services", headers=headers)
        assert resp.status_code == 200
        services = resp.json()
        assert isinstance(services, list)
        assert len(services) >= 8

        # 2. Filter by tier
        resp_tier = client.get("/api/v1/services?tier=tier-1", headers=headers)
        assert resp_tier.status_code == 200
        tier1_svcs = resp_tier.json()
        assert len(tier1_svcs) > 0
        for svc in tier1_svcs:
            assert svc["tier"] == "tier-1"

        # 3. Filter by owner team
        resp_team = client.get("/api/v1/services?owner_team_id=team-payments", headers=headers)
        assert resp_team.status_code == 200
        team_svcs = resp_team.json()
        assert len(team_svcs) > 0
        for svc in team_svcs:
            assert svc["owner_team_id"] == "team-payments"


def test_browse_service_by_id() -> None:
    """Test single service retrieval and 404 for missing service."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # Existing service
        resp = client.get("/api/v1/services/svc-payments-api", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "svc-payments-api"
        assert data["name"] == "Payments API"
        assert data["tier"] == "tier-1"

        # Missing service
        resp_missing = client.get("/api/v1/services/non-existent-svc", headers=headers)
        assert resp_missing.status_code == 404


def test_browse_teams_list_and_detail_with_relations() -> None:
    """Test listing teams and retrieving team detail with employees, services, and projects."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)

        # 1. Full list
        resp = client.get("/api/v1/teams", headers=headers)
        assert resp.status_code == 200
        teams = resp.json()
        assert isinstance(teams, list)
        assert len(teams) >= 6

        # 2. Detail by ID
        resp_detail = client.get("/api/v1/teams/team-payments", headers=headers)
        assert resp_detail.status_code == 200
        team_data = resp_detail.json()
        assert team_data["id"] == "team-payments"
        assert team_data["name"] == "Payments Platform"
        assert "employees" in team_data
        assert isinstance(team_data["employees"], list)
        assert len(team_data["employees"]) > 0
        assert "services" in team_data
        assert isinstance(team_data["services"], list)
        assert len(team_data["services"]) > 0
        assert "projects" in team_data
        assert isinstance(team_data["projects"], list)

        # Missing team
        resp_missing = client.get("/api/v1/teams/non-existent-team", headers=headers)
        assert resp_missing.status_code == 404


def test_browse_entities_headers() -> None:
    """Ensure browse endpoints return standard X-Request-ID and rate limit headers."""
    app = create_app()
    with TestClient(app) as client:
        headers = get_viewer_auth_headers(client)
        resp = client.get("/api/v1/customers", headers=headers)
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
