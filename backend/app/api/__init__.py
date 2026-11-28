"""API package for NovaEnterprise."""

from backend.app.api.auth import router as auth_router
from backend.app.api.customers import router as customers_router
from backend.app.api.decisions import router as decisions_router
from backend.app.api.documents import router as documents_router
from backend.app.api.graph import router as graph_router
from backend.app.api.health import router as health_router
from backend.app.api.incidents import router as incidents_router
from backend.app.api.projects import router as projects_router
from backend.app.api.research import router as research_router
from backend.app.api.services import router as services_router
from backend.app.api.teams import router as teams_router
from backend.app.api.tickets import router as tickets_router

__all__ = [
    "auth_router",
    "customers_router",
    "decisions_router",
    "documents_router",
    "graph_router",
    "health_router",
    "incidents_router",
    "projects_router",
    "research_router",
    "services_router",
    "teams_router",
    "tickets_router",
]
