"""Repository layer package for NovaEnterprise.

Encapsulates all direct database queries, filters, pagination, and relational operations
using SQLAlchemy. Repositories must never be imported directly by agents.
"""

from backend.app.repositories.base import BaseRepository
from backend.app.repositories.documents import (
    ApprovalRequestRepository,
    DocumentChunkRepository,
    DocumentRepository,
)
from backend.app.repositories.domain import (
    CustomerRepository,
    DecisionRepository,
    EmployeeRepository,
    IncidentRepository,
    ProjectRepository,
    ServiceRepository,
    TeamRepository,
    TicketRepository,
)
from backend.app.repositories.research import (
    CitationRecordRepository,
    ResearchSessionRepository,
    WorkflowEventRepository,
)
from backend.app.repositories.security import (
    AuditLogRepository,
    UserRepository,
)

__all__ = [
    "ApprovalRequestRepository",
    "AuditLogRepository",
    "BaseRepository",
    "CitationRecordRepository",
    "CustomerRepository",
    "DecisionRepository",
    "DocumentChunkRepository",
    "DocumentRepository",
    "EmployeeRepository",
    "IncidentRepository",
    "ProjectRepository",
    "ResearchSessionRepository",
    "ServiceRepository",
    "TeamRepository",
    "TicketRepository",
    "UserRepository",
    "WorkflowEventRepository",
]
