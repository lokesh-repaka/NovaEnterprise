"""Unit tests for request context middleware (N5).

Verifies X-Request-ID generation, preservation, propagation, and log correlation.
"""

import io
import json
import logging
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.app.core.logging import (
    JSONFormatter,
    get_logger,
    get_request_id,
)
from backend.app.middleware.request_context import RequestContextMiddleware


@pytest.fixture
def test_app() -> FastAPI:
    """Create a minimal FastAPI test app equipped with RequestContextMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test/context")
    async def context_endpoint(request: Request):
        return {
            "state_request_id": getattr(request.state, "request_id", None),
            "ctx_request_id": get_request_id(),
        }

    @app.get("/test/logging")
    async def logging_endpoint(request: Request):
        logger = get_logger("test.route")
        logger.info("Executing request inside route handler")
        return {"ok": True}

    return app


def test_request_id_generated_when_missing(test_app: FastAPI):
    """Test that a valid UUID4 X-Request-ID is generated and returned when not provided."""
    client = TestClient(test_app)
    response = client.get("/test/context")

    assert response.status_code == 200
    assert "x-request-id" in response.headers or "X-Request-ID" in response.headers
    req_id = response.headers.get("x-request-id") or response.headers.get(
        "X-Request-ID"
    )
    assert req_id is not None

    # Verify req_id is a valid UUID4
    parsed_uuid = uuid.UUID(req_id, version=4)
    assert str(parsed_uuid) == req_id

    # Verify route handler received the same request ID
    data = response.json()
    assert data["state_request_id"] == req_id
    assert data["ctx_request_id"] == req_id


def test_request_id_preserved_when_provided(test_app: FastAPI):
    """Test that incoming client-provided X-Request-ID is preserved across lifecycle."""
    client = TestClient(test_app)
    custom_id = "client-trace-abc-12345"
    response = client.get("/test/context", headers={"X-Request-ID": custom_id})

    assert response.status_code == 200
    returned_id = response.headers.get("x-request-id") or response.headers.get(
        "X-Request-ID"
    )
    assert returned_id == custom_id

    data = response.json()
    assert data["state_request_id"] == custom_id
    assert data["ctx_request_id"] == custom_id


def test_request_id_regenerated_if_empty(test_app: FastAPI):
    """Test that an empty or whitespace-only X-Request-ID is replaced with a valid UUID4."""
    client = TestClient(test_app)
    response = client.get("/test/context", headers={"X-Request-ID": "   "})

    assert response.status_code == 200
    returned_id = response.headers.get("x-request-id") or response.headers.get(
        "X-Request-ID"
    )
    assert returned_id is not None
    assert returned_id.strip() != ""
    # Should be valid UUID
    uuid.UUID(returned_id, version=4)


def test_request_id_in_structured_logs(test_app: FastAPI):
    """Test that structured JSON logs emitted inside request lifecycle include request_id (N5)."""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    try:
        client = TestClient(test_app)
        custom_id = "log-trace-uuid-9999"
        response = client.get("/test/logging", headers={"X-Request-ID": custom_id})

        assert response.status_code == 200

        output = log_capture.getvalue()
        lines = [line.strip() for line in output.strip().split("\n") if line.strip()]
        assert len(lines) > 0

        # Parse log records and find our message
        route_logs = [
            json.loads(line)
            for line in lines
            if "Executing request inside route handler" in line
        ]
        assert len(route_logs) == 1
        log_entry = route_logs[0]
        assert log_entry["request_id"] == custom_id
    finally:
        root_logger.handlers = old_handlers
