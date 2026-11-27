"""Main application entry point for NovaEnterprise.

Configures FastAPI application, middleware pipeline, unprefixed health routes,
and API routers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.auth import router as auth_router
from backend.app.api.customers import router as customers_router
from backend.app.api.health import router as health_router
from backend.app.api.incidents import router as incidents_router
from backend.app.api.services import router as services_router
from backend.app.api.teams import router as teams_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.db import init_db
from backend.app.core.logging import get_logger, setup_logging
from backend.app.middleware.audit import AuditMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_context import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    settings = get_settings()
    # Configure structured logging on startup
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger = get_logger("app.main")
    logger.info(
        "Starting %s v%s in %s environment (offline: %s)",
        settings.app_name,
        settings.app_version,
        settings.environment,
        settings.llm_provider == "fake",
    )
    # Ensure database tables are initialized
    init_db()
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="NovaEnterprise: Enterprise Knowledge & Decision Intelligence Platform",
        lifespan=lifespan,
    )

    # =========================================================================
    # Canonical Middleware Pipeline Order (P3-4 / Claude.md §10)
    # In Starlette, middlewares execute in reverse order of addition:
    #   Request Context (outermost) -> CORS -> Rate Limit -> Audit (innermost) -> Endpoint
    # =========================================================================

    # 1. Audit Logging Middleware (Innermost: records state modifications after rate limiting)
    app.add_middleware(AuditMiddleware)

    # 2. Rate Limiting Middleware (Redis token-bucket - N6: blocks excessive requests before audit)
    app.add_middleware(RateLimitMiddleware)

    # 3. CORS Middleware (evaluates cross-origin requests & preflight OPTIONS)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 4. Request Context & Tracking Middleware (Outermost: ensures X-Request-ID on all responses - N5)
    app.add_middleware(RequestContextMiddleware)

    # 3. Unprefixed Health Routes (/health, /health/ready - Claude.md §10)
    app.include_router(health_router)

    # 4. API v1 Routers (/api/v1/auth, /api/v1/customers, etc. - Claude.md §12)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(customers_router, prefix=settings.api_v1_prefix)
    app.include_router(incidents_router, prefix=settings.api_v1_prefix)
    app.include_router(services_router, prefix=settings.api_v1_prefix)
    app.include_router(teams_router, prefix=settings.api_v1_prefix)

    return app


# Default app instance for ASGI servers (e.g. uvicorn backend.app.main:app)
app = create_app()
