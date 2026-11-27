"""API package for NovaEnterprise."""

from backend.app.api.auth import router as auth_router
from backend.app.api.customers import router as customers_router
from backend.app.api.health import router as health_router
from backend.app.api.incidents import router as incidents_router
from backend.app.api.services import router as services_router
from backend.app.api.teams import router as teams_router

__all__ = [
    "auth_router",
    "customers_router",
    "health_router",
    "incidents_router",
    "services_router",
    "teams_router",
]
