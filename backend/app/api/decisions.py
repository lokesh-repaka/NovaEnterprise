"""Architectural Decision Record (ADR) browse API routes (P4-3).

Provides endpoints for listing, filtering, and retrieving ADR decisions.
Protected by require_role("viewer") RBAC guard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.domain import DecisionRepository
from backend.app.schemas.entities import DecisionResponse

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get(
    "",
    response_model=list[DecisionResponse],
    summary="List architectural decisions (ADRs)",
    description="Retrieve a paginated list of Architectural Decision Records with optional status and incident filters.",
)
def list_decisions(
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by decision status (proposed, accepted, approved, deprecated)",
    ),
    incident_id: str | None = Query(
        None, description="Filter by associated incident ID"
    ),
) -> list[DecisionResponse]:
    """List decision records matching criteria."""
    repo = DecisionRepository(db)
    decisions = repo.list_decisions(
        skip=skip,
        limit=limit,
        status=status_filter,
        incident_id=incident_id,
    )
    return [DecisionResponse.model_validate(d) for d in decisions]


@router.get(
    "/{decision_id}",
    response_model=DecisionResponse,
    summary="Get architectural decision by ID",
    description="Retrieve a single Architectural Decision Record by unique ADR ID.",
)
def get_decision(
    decision_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
) -> DecisionResponse:
    """Retrieve decision details by unique ADR ID."""
    repo = DecisionRepository(db)
    decision = repo.get(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )
    return DecisionResponse.model_validate(decision)
