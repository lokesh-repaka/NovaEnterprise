"""API integration tests for Knowledge Graph Explorer and read-only Cypher queries (P11-1, F14, Claude.md §8, §18.1).

Tests:
- GET  /api/v1/graph: Browse knowledge graph with limit and label filters [viewer+]
- GET  /api/v1/graph/expand/{id}: 1-hop neighbor expansion with directions (in, out, both) and relationship filtering [viewer+]
- 404 Not Found on expand for non-existent node ID
- 422 Unprocessable Entity for invalid expansion direction parameter
- POST /api/v1/graph/query: Execute read-only Cypher queries [analyst+, admin]
- RBAC enforcement: viewer gets 403 on POST /api/v1/graph/query
- 401 Unauthorized for unauthenticated requests
- Security Guardrail: Write mutations (CREATE, MERGE, DELETE, SET, DROP) and multi-statements rejected with 400 Bad Request
"""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.main import create_app
from backend.app.services.graph_service import reset_graph_service
from backend.app.services.seed import seed_database
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store, reset_graph_store


def setup_module() -> None:
    """Initialize database and seed graph store for isolated offline test run."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        seed_database(session)

    # Seed in-memory graph store with domain entities
    reset_graph_store()
    reset_graph_service()
    store = get_graph_store()
    if isinstance(store, InMemoryGraphStore):
        sample_dir = Path(__file__).resolve().parents[2] / "sample_data"
        seed_graph_from_domain(store, sample_data_dir=sample_dir)


def get_auth_headers(client: TestClient, role: str) -> dict[str, str]:
    """Helper to acquire signed demo JWT for a specific role."""
    resp = client.post("/api/v1/auth/demo-token", json={"role": role})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_graph_endpoints_unauthenticated_return_401() -> None:
    """Ensure all graph endpoints reject unauthenticated calls with 401."""
    app = create_app()
    with TestClient(app) as client:
        # GET /graph
        resp = client.get("/api/v1/graph")
        assert resp.status_code == 401

        # GET /graph/expand/{id}
        resp = client.get("/api/v1/graph/expand/svc-payments-api")
        assert resp.status_code == 401

        # POST /graph/query
        resp = client.post(
            "/api/v1/graph/query",
            json={"query": "MATCH (s:Service) RETURN s"},
        )
        assert resp.status_code == 401


def test_graph_query_rbac_viewer_forbidden_403() -> None:
    """Ensure viewer role can browse graph and expand nodes, but is forbidden (403) from running Cypher."""
    app = create_app()
    with TestClient(app) as client:
        viewer_headers = get_auth_headers(client, "viewer")

        # Viewer can browse
        resp_browse = client.get("/api/v1/graph", headers=viewer_headers)
        assert resp_browse.status_code == 200

        # Viewer can expand
        resp_expand = client.get(
            "/api/v1/graph/expand/svc-payments-api", headers=viewer_headers
        )
        assert resp_expand.status_code == 200

        # Viewer CANNOT execute arbitrary Cypher queries (Claude.md §2, §18.1)
        resp_query = client.post(
            "/api/v1/graph/query",
            json={"query": "MATCH (s:Service) RETURN s"},
            headers=viewer_headers,
        )
        assert resp_query.status_code == 403
        assert "forbidden" in resp_query.json()["detail"].lower()


def test_graph_browse_subgraph_and_label_filtering() -> None:
    """Verify browsing graph subgraph, respecting limit and node_label filters (F14)."""
    app = create_app()
    with TestClient(app) as client:
        viewer_headers = get_auth_headers(client, "viewer")

        # 1. Browse all nodes/edges
        resp = client.get("/api/v1/graph?limit=50", headers=viewer_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0

        # Verify node shape
        first_node = data["nodes"][0]
        assert "id" in first_node
        assert "label" in first_node
        assert "properties" in first_node

        # Verify edge shape
        first_edge = data["edges"][0]
        assert "source" in first_edge
        assert "target" in first_edge
        assert "type" in first_edge

        # 2. Filter by node_label=Service
        service_resp = client.get(
            "/api/v1/graph?node_label=Service", headers=viewer_headers
        )
        assert service_resp.status_code == 200
        services_data = service_resp.json()
        assert all(n["label"] == "Service" for n in services_data["nodes"])
        assert any(n["id"] == "svc-payments-api" for n in services_data["nodes"])

        # 3. Limit parameter
        limit_resp = client.get("/api/v1/graph?limit=3", headers=viewer_headers)
        assert limit_resp.status_code == 200
        assert len(limit_resp.json()["nodes"]) <= 3


def test_graph_expand_node_lifecycle_and_directions() -> None:
    """Verify 1-hop node expansion with directions and relationship filters (F14)."""
    app = create_app()
    with TestClient(app) as client:
        viewer_headers = get_auth_headers(client, "viewer")

        # 1. Expand Incident inc-2031 (Payments API Outage) - direction=both
        resp_both = client.get(
            "/api/v1/graph/expand/inc-2031?direction=both", headers=viewer_headers
        )
        assert resp_both.status_code == 200
        data_both = resp_both.json()

        assert data_both["root"] is not None
        assert data_both["root"]["id"] == "inc-2031"
        assert data_both["root"]["label"] == "Incident"

        # Check connecting nodes: impacted customers and affected service
        node_ids = {n["id"] for n in data_both["nodes"]}
        assert "inc-2031" in node_ids
        assert "svc-payments-api" in node_ids

        edge_types = {e["type"] for e in data_both["edges"]}
        assert "AFFECTED" in edge_types or "IMPACTED" in edge_types

        # 2. Expand with direction=out
        resp_out = client.get(
            "/api/v1/graph/expand/inc-2031?direction=out", headers=viewer_headers
        )
        assert resp_out.status_code == 200
        for edge in resp_out.json()["edges"]:
            assert edge["source"] == "inc-2031"

        # 3. Expand with relationship_type=AFFECTED
        resp_rel = client.get(
            "/api/v1/graph/expand/inc-2031?relationship_type=AFFECTED",
            headers=viewer_headers,
        )
        assert resp_rel.status_code == 200
        for edge in resp_rel.json()["edges"]:
            assert edge["type"] == "AFFECTED"


def test_graph_expand_nonexistent_node_returns_404() -> None:
    """Ensure expanding a non-existent node returns 404 Not Found."""
    app = create_app()
    with TestClient(app) as client:
        viewer_headers = get_auth_headers(client, "viewer")
        resp = client.get(
            "/api/v1/graph/expand/unknown-node-404", headers=viewer_headers
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


def test_graph_expand_invalid_direction_returns_422() -> None:
    """Ensure invalid direction parameter triggers 422 Unprocessable Entity."""
    app = create_app()
    with TestClient(app) as client:
        viewer_headers = get_auth_headers(client, "viewer")
        resp = client.get(
            "/api/v1/graph/expand/svc-payments-api?direction=sideways",
            headers=viewer_headers,
        )
        assert resp.status_code == 422


def test_cypher_query_execution_analyst_and_admin() -> None:
    """Verify analyst and admin can execute valid read-only Cypher queries (F14)."""
    app = create_app()
    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")
        admin_headers = get_auth_headers(client, "admin")

        # 1. Analyst executing read-only MATCH query
        resp = client.post(
            "/api/v1/graph/query",
            json={"query": "MATCH (s:Service) RETURN s"},
            headers=analyst_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "execution_time_ms" in data
        assert data["execution_time_ms"] >= 0
        assert len(data["results"]) >= 1

        # 2. Admin executing parameterized read-only query
        resp_admin = client.post(
            "/api/v1/graph/query",
            json={
                "query": "MATCH (s:Service) RETURN s",
                "parameters": {"tier": "tier-1"},
            },
            headers=admin_headers,
        )
        assert resp_admin.status_code == 200
        data_admin = resp_admin.json()
        assert len(data_admin["results"]) >= 1
        assert all(
            r.get("properties", {}).get("tier") == "tier-1"
            for r in data_admin["results"]
        )


def test_cypher_query_security_mutations_blocked_400() -> None:
    """Verify write mutations, administrative calls, and multi-statement queries are blocked with 400 (Claude.md §18.1)."""
    app = create_app()
    with TestClient(app) as client:
        analyst_headers = get_auth_headers(client, "analyst")

        mutations = [
            "CREATE (n:Malicious {name: 'Exploit'}) RETURN n",
            "MATCH (n:Service) DELETE n RETURN n",
            "MATCH (n:Service) SET n.compromised = true RETURN n",
            "MATCH (n:Service) REMOVE n.tier RETURN n",
            "MATCH (n:Service) MERGE (m:Exploit) RETURN n",
            "DROP INDEX ON :Service(name)",
            "MATCH (n:Service) RETURN n; DROP TABLE services",
            "CALL dbms.security.createUser('hacker', 'pass', false)",
            "LOAD CSV FROM 'file:///etc/passwd' AS line RETURN line",
            "",
            "   ",
            "// only comments\n",
        ]

        for query in mutations:
            resp = client.post(
                "/api/v1/graph/query",
                json={"query": query},
                headers=analyst_headers,
            )
            assert resp.status_code == 400, (
                f"Expected 400 for mutating query: {query}, got {resp.status_code}"
            )
            assert "invalid" in resp.json()["detail"].lower()
