"""Unit tests for health and readiness routes (N4, N5).

Verifies /health (liveness) and /health/ready (readiness adapter check) unprefixed routes.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.api.health import (
    check_database_health,
    check_graph_store_health,
    check_llm_health,
    check_redis_health,
    check_vector_store_health,
)
from backend.app.core.config import Settings
from backend.app.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client against the NovaEnterprise main FastAPI app."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_liveness(client: TestClient):
    """Test that /health returns 200 OK with status ok and carries X-Request-ID (N5)."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
    assert "x-request-id" in response.headers or "X-Request-ID" in response.headers


def test_health_ready_default_offline(client: TestClient):
    """Test that /health/ready returns 200 with status 'ready' and all store checks in offline mode (N1, N4)."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ready"
    assert "checks" in data

    checks = data["checks"]
    assert "database" in checks
    assert "redis" in checks
    assert "vector_store" in checks
    assert "graph_store" in checks
    assert "llm" in checks

    assert checks["database"]["status"] == "ok"
    assert "sqlite" in checks["database"]["detail"].lower()

    assert checks["redis"]["status"] == "ok"
    assert "fakeredis" in checks["redis"]["detail"].lower()

    assert checks["vector_store"]["status"] == "ok"
    assert "memory" in checks["vector_store"]["detail"].lower()

    assert checks["graph_store"]["status"] == "ok"
    assert "memory" in checks["graph_store"]["detail"].lower()

    assert checks["llm"]["status"] == "ok"
    assert checks["llm"]["detail"]["llm_provider"] == "fake"

    assert "x-request-id" in response.headers or "X-Request-ID" in response.headers


def test_health_ready_degraded_when_check_fails():
    """Test that /health/ready returns status 'degraded' when a store fails (not 500 error)."""
    with patch("backend.app.api.health.check_database_health") as mock_db:
        mock_db.return_value = {"status": "degraded", "detail": "connection timed out"}

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/health/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["database"]["status"] == "degraded"
            assert "timed out" in data["checks"]["database"]["detail"]
            # Other checks should still be reported
            assert data["checks"]["llm"]["status"] == "ok"


def test_health_ready_with_configured_adapters():
    """Test /health/ready reporting external adapter details when configured."""
    custom_settings = Settings(
        vector_store="qdrant",
        qdrant_url="http://qdrant.internal:6333",
        graph_store="neo4j",
        neo4j_uri="bolt://neo4j.internal:7687",
        llm_provider="anthropic",
        use_fakeredis=False,
        redis_url="redis://redis.internal:6379/0",
        database_url="postgresql://user:pass@db.internal:5432/enterprise",
    )

    with (
        patch("backend.app.api.health.get_settings", return_value=custom_settings),
        patch(
            "backend.app.api.health.check_redis_health",
            return_value={
                "status": "ok",
                "detail": "redis: redis://redis.internal:6379/0",
            },
        ),
    ):
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/health/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert (
                data["checks"]["vector_store"]["detail"]
                == "qdrant http://qdrant.internal:6333"
            )
            assert (
                data["checks"]["graph_store"]["detail"]
                == "neo4j bolt://neo4j.internal:7687"
            )
            assert data["checks"]["llm"]["detail"]["llm_provider"] == "anthropic"
            assert "database: postgresql" in data["checks"]["database"]["detail"]


def test_check_functions_direct_coverage():
    """Directly test adapter check functions for edge cases and exceptions."""
    # 1. Database exceptions
    bad_settings = MagicMock(spec=Settings)
    bad_settings.database_url = "sqlite:///./data/test.db"
    type(bad_settings).database_url = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("Disk I/O error"))
    )
    db_res = check_database_health(bad_settings)
    assert db_res["status"] == "degraded"
    assert "Disk I/O error" in db_res["detail"]

    # 2. Redis external and exception
    redis_settings = Settings(use_fakeredis=False, redis_url="redis://localhost:6379/0")
    redis_res = check_redis_health(redis_settings)
    assert redis_res["status"] == "ok"
    assert "redis://localhost:6379/0" in redis_res["detail"]

    bad_redis = MagicMock(spec=Settings)
    bad_redis.use_fakeredis = False
    type(bad_redis).redis_url = property(
        lambda self: (_ for _ in ()).throw(ConnectionError("Refused"))
    )
    bad_redis_res = check_redis_health(bad_redis)
    assert bad_redis_res["status"] == "degraded"
    assert "Refused" in bad_redis_res["detail"]

    # 3. Vector store custom and exception
    custom_vec = Settings(vector_store="custom")
    assert check_vector_store_health(custom_vec)["detail"] == "custom store"

    bad_vec = MagicMock(spec=Settings)
    type(bad_vec).vector_store = property(
        lambda self: (_ for _ in ()).throw(ValueError("Invalid vector backend"))
    )
    bad_vec_res = check_vector_store_health(bad_vec)
    assert bad_vec_res["status"] == "degraded"
    assert "Invalid vector backend" in bad_vec_res["detail"]

    # 4. Graph store custom and exception
    custom_graph = Settings(graph_store="custom")
    assert check_graph_store_health(custom_graph)["detail"] == "custom store"

    bad_graph = MagicMock(spec=Settings)
    type(bad_graph).graph_store = property(
        lambda self: (_ for _ in ()).throw(ValueError("Invalid graph backend"))
    )
    bad_graph_res = check_graph_store_health(bad_graph)
    assert bad_graph_res["status"] == "degraded"
    assert "Invalid graph backend" in bad_graph_res["detail"]

    # 5. LLM unsupported and exception
    unsupported_llm = Settings(llm_provider="unsupported_xyz")
    llm_res = check_llm_health(unsupported_llm)
    assert llm_res["status"] == "degraded"
    assert "unsupported provider" in llm_res["detail"]

    bad_llm = MagicMock(spec=Settings)
    type(bad_llm).llm_provider = property(
        lambda self: (_ for _ in ()).throw(TypeError("LLM error"))
    )
    bad_llm_res = check_llm_health(bad_llm)
    assert bad_llm_res["status"] == "degraded"
    assert "LLM error" in bad_llm_res["detail"]
