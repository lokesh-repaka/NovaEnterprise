"""API package for NovaEnterprise."""

from backend.app.api.health import router as health_router

__all__ = ["health_router"]
