"""Services layer package for NovaEnterprise.

Encapsulates application workflows, seeding, state persistence, and memory orchestration.
Services must never import from HTTP/FastAPI layer.
"""

from backend.app.services.research_service import (
    ResearchService,
    get_research_service,
    reset_research_service,
)
from backend.app.services.seed import (
    get_fiscal_calendar,
    load_all_documents,
    load_json_data,
    resolve_fiscal_quarter,
    seed_database,
)

__all__ = [
    "ResearchService",
    "get_fiscal_calendar",
    "get_research_service",
    "load_all_documents",
    "load_json_data",
    "reset_research_service",
    "resolve_fiscal_quarter",
    "seed_database",
]
