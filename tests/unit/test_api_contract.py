"""Unit tests for docs/API_CONTRACT.md specification validity and completeness (P4-1).

Validates that the authoritative API contract exists, covers all required
endpoint groups, RBAC authorization tiers, global headers, the unified
Evidence shape, and TypeScript definitions for Phase 12 frontend integration.
"""

from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "API_CONTRACT.md"


def test_api_contract_exists_and_non_empty() -> None:
    """Ensure docs/API_CONTRACT.md exists and is substantive."""
    assert CONTRACT_PATH.exists(), f"API contract file not found at {CONTRACT_PATH}"
    content = CONTRACT_PATH.read_text(encoding="utf-8")
    assert len(content.strip()) > 1000, "API contract document must be substantive (>1000 chars)"


def test_api_contract_covers_global_headers_and_status_codes() -> None:
    """Ensure standard headers and HTTP status codes are documented."""
    assert CONTRACT_PATH.exists(), "API contract does not exist"
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    # Global headers
    assert "X-Request-ID" in content
    assert "X-RateLimit-Limit" in content
    assert "X-RateLimit-Remaining" in content
    assert "X-RateLimit-Reset" in content
    assert "Authorization: Bearer" in content

    # HTTP status codes
    assert "200 OK" in content
    assert "201 Created" in content
    assert "202 Accepted" in content
    assert "400 Bad Request" in content
    assert "401 Unauthorized" in content
    assert "403 Forbidden" in content
    assert "404 Not Found" in content
    assert "422 Unprocessable Entity" in content
    assert "429 Too Many Requests" in content
    assert "500 Internal Server Error" in content


def test_api_contract_covers_all_endpoint_routes() -> None:
    """Verify all system routes are cataloged with HTTP method and path."""
    assert CONTRACT_PATH.exists(), "API contract does not exist"
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    expected_routes = [
        # Health
        "GET /health",
        "GET /health/ready",
        # Auth (P3-2)
        "GET /api/v1/auth/demo-users",
        "POST /api/v1/auth/demo-token",
        "POST /api/v1/auth/login",
        "POST /api/v1/auth/token",
        "GET /api/v1/auth/me",
        # Browse Entities (P4-2 & P4-3)
        "GET /api/v1/customers",
        "GET /api/v1/customers/{id}",
        "GET /api/v1/incidents",
        "GET /api/v1/incidents/{id}",
        "GET /api/v1/services",
        "GET /api/v1/services/{id}",
        "GET /api/v1/teams",
        "GET /api/v1/teams/{id}",
        "GET /api/v1/decisions",
        "GET /api/v1/decisions/{id}",
        "GET /api/v1/projects",
        "GET /api/v1/projects/{id}",
        "GET /api/v1/tickets",
        "GET /api/v1/tickets/{id}",
        # Research Engine (Phase 10)
        "POST /api/v1/research",
        "GET /api/v1/research/{session_id}",
        "GET /api/v1/research/{session_id}/events",
        # Knowledge Graph (Phase 11)
        "GET /api/v1/graph",
        "GET /api/v1/graph/expand/{id}",
        "POST /api/v1/graph/query",
        # Documents & Approvals (Phase 11)
        "POST /api/v1/documents/upload",
        "GET /api/v1/documents",
        "GET /api/v1/documents/{id}",
        "DELETE /api/v1/documents/{id}",
        "GET /api/v1/approvals",
        "POST /api/v1/approvals/{id}/decide",
    ]

    for route in expected_routes:
        assert route in content, f"Route '{route}' missing from API_CONTRACT.md"


def test_api_contract_covers_rbac_matrix() -> None:
    """Verify RBAC access roles are documented for endpoints."""
    assert CONTRACT_PATH.exists(), "API contract does not exist"
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "viewer" in content
    assert "analyst" in content
    assert "admin" in content
    assert "Public" in content


def test_api_contract_contains_evidence_shape_contract() -> None:
    """Verify the single canonical Evidence shape (Claude.md Section 5) is defined."""
    assert CONTRACT_PATH.exists(), "API contract does not exist"
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "source_type" in content
    assert "locator" in content
    assert "content" in content
    assert "score" in content
    assert "metadata" in content


def test_api_contract_includes_typescript_client_types() -> None:
    """Verify TypeScript types block exists to unblock Phase 12 frontend."""
    assert CONTRACT_PATH.exists(), "API contract does not exist"
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "```typescript" in content
    assert "export interface Customer" in content or "export interface CustomerResponse" in content
    assert "export interface Incident" in content or "export interface IncidentResponse" in content
    assert "export interface Service" in content or "export interface ServiceResponse" in content
    assert "export interface ResearchSession" in content
    assert "export interface WorkflowEvent" in content
