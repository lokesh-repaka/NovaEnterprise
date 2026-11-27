"""Main application entry point for NovaEnterprise.

Configures FastAPI application, middleware pipeline, unprefixed health routes,
and API routers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.health import router as health_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger, setup_logging
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

    # 1. Request Context & Tracking Middleware (X-Request-ID propagation - N5)
    app.add_middleware(RequestContextMiddleware)

    # 2. CORS Middleware
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 3. Unprefixed Health Routes (/health, /health/ready - Claude.md §10)
    app.include_router(health_router)

    return app


# Default app instance for ASGI servers (e.g. uvicorn backend.app.main:app)
app = create_app()
