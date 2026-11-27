"""Issue and task ticket browse API routes (P4-3).

Provides endpoints for listing, filtering, and retrieving tracked project tickets.
Protected by require_role("viewer") RBAC guard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.domain import TicketRepository
from backend.app.schemas.entities import TicketResponse

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get(
    "",
    response_model=list[TicketResponse],
    summary="List issue and task tickets",
    description="Retrieve a paginated list of tickets with optional status, priority, project, and assignee filters.",
)
def list_tickets(
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by ticket status (open, in_progress, resolved, closed)",
    ),
    priority: str | None = Query(
        None, description="Filter by ticket priority (P0, P1, P2, P3)"
    ),
    project_id: str | None = Query(None, description="Filter by associated project ID"),
    assignee_id: str | None = Query(None, description="Filter by assigned employee ID"),
) -> list[TicketResponse]:
    """List ticket records matching criteria."""
    repo = TicketRepository(db)
    tickets = repo.list_tickets(
        skip=skip,
        limit=limit,
        status=status_filter,
        priority=priority,
        project_id=project_id,
        assignee_id=assignee_id,
    )
    return [TicketResponse.model_validate(t) for t in tickets]


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket by ID",
    description="Retrieve a single ticket by its unique ticket ID.",
)
def get_ticket(
    ticket_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
) -> TicketResponse:
    """Retrieve ticket details by unique ticket ID."""
    repo = TicketRepository(db)
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found",
        )
    return TicketResponse.model_validate(ticket)
