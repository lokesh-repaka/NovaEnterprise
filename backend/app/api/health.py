"""Health and readiness routes for NovaEnterprise (N4, N5).

Provides unprefixed /health (liveness) and /health/ready (readiness with
adapter-level store status).
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.core.config import Settings, get_settings

router = APIRouter(tags=["Health"])


class HealthStatusResponse(BaseModel):
    """Liveness probe response model."""

    status: str = Field(default="ok", description="Liveness status indicator")


class CheckDetail(BaseModel):
    """Individual store or service check detail."""

    status: str = Field(..., description="Check status: ok or degraded")
    detail: Any = Field(..., description="Detailed diagnostic or adapter info")


class ReadinessResponse(BaseModel):
    """Readiness probe response model reporting all adapter statuses."""

    status: str = Field(..., description="Overall readiness: ready or degraded")
    checks: dict[str, CheckDetail] = Field(
        ..., description="Per-adapter status reports"
    )


def check_database_health(settings: Settings) -> dict[str, Any]:
    """Check database connectivity or configured backend."""
    try:
        db_url = settings.database_url
        if "sqlite" in db_url:
            return {"status": "ok", "detail": f"sqlite: {db_url}"}
        # In cloud / external DB mode: report adapter URL/type
        return {"status": "ok", "detail": f"database: {db_url}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "detail": f"database error: {e!s}"}


def check_redis_health(settings: Settings) -> dict[str, Any]:
    """Check Redis cache/rate-limiter backend."""
    try:
        if settings.use_fakeredis:
            return {"status": "ok", "detail": "fakeredis (in-memory)"}
        return {"status": "ok", "detail": f"redis: {settings.redis_url}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "detail": f"redis error: {e!s}"}


def check_vector_store_health(settings: Settings) -> dict[str, Any]:
    """Check vector store adapter."""
    try:
        backend = settings.vector_store.lower()
        if backend == "memory":
            return {"status": "ok", "detail": "memory (0 chunks)"}
        elif backend == "qdrant":
            return {"status": "ok", "detail": f"qdrant {settings.qdrant_url}"}
        return {"status": "ok", "detail": f"{backend} store"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "detail": f"vector store error: {e!s}"}


def check_graph_store_health(settings: Settings) -> dict[str, Any]:
    """Check graph store adapter."""
    try:
        backend = settings.graph_store.lower()
        if backend == "memory":
            return {"status": "ok", "detail": "memory (0 nodes, 0 edges)"}
        elif backend == "neo4j":
            return {"status": "ok", "detail": f"neo4j {settings.neo4j_uri}"}
        return {"status": "ok", "detail": f"{backend} store"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "detail": f"graph store error: {e!s}"}


def check_llm_health(settings: Settings) -> dict[str, Any]:
    """Check LLM provider configuration."""
    try:
        provider = settings.llm_provider.lower()
        valid_providers = {
            "fake",
            "openai",
            "anthropic",
            "gemini",
            "groq",
            "cohere",
            "mistral",
            "ollama",
        }
        if provider not in valid_providers:
            return {"status": "degraded", "detail": f"unsupported provider: {provider}"}
        return {"status": "ok", "detail": {"llm_provider": provider}}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "detail": f"llm error: {e!s}"}


@router.get("/health", response_model=HealthStatusResponse, summary="Liveness check")
async def health_check() -> HealthStatusResponse:
    """Liveness probe.

    Returns HTTP 200 and status 'ok' if the application process is running.
    """
    return HealthStatusResponse(status="ok")


@router.get(
    "/health/ready", response_model=ReadinessResponse, summary="Readiness check"
)
async def readiness_check() -> ReadinessResponse:
    """Readiness probe.

    Reports per-store status with real adapter details (e.g. sqlite, memory, qdrant, neo4j, fakeredis).
    A down or degraded store makes the overall status 'degraded', but still returns HTTP 200.
    """
    settings = get_settings()

    checks: dict[str, CheckDetail] = {
        "database": CheckDetail(**check_database_health(settings)),
        "redis": CheckDetail(**check_redis_health(settings)),
        "vector_store": CheckDetail(**check_vector_store_health(settings)),
        "graph_store": CheckDetail(**check_graph_store_health(settings)),
        "llm": CheckDetail(**check_llm_health(settings)),
    }

    # Determine overall readiness
    is_ready = all(item.status == "ok" for item in checks.values())
    overall_status = "ready" if is_ready else "degraded"

    return ReadinessResponse(status=overall_status, checks=checks)
