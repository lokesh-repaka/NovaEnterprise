"""Team domain browse API routes (P4-2).

Provides endpoints for listing and retrieving engineering/operational teams,
including member employees, owned microservices, and active projects.
Protected by require_role("viewer") RBAC guard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.domain import Team
from backend.app.repositories.domain import TeamRepository
from backend.app.schemas.entities import TeamDetailResponse, TeamResponse

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get(
    "",
    response_model=list[TeamResponse],
    summary="List engineering teams",
    description="Retrieve a paginated list of organizational engineering and operational teams.",
)
def list_teams(
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
) -> list[TeamResponse]:
    """List team records ordered by name."""
    repo = TeamRepository(db)
    teams = repo.list(skip=skip, limit=limit, order_by=Team.name)
    return [TeamResponse.model_validate(t) for t in teams]


@router.get(
    "/{team_id}",
    response_model=TeamDetailResponse,
    summary="Get team by ID",
    description="Retrieve team details including member employees, owned services, and active projects.",
)
def get_team(
    team_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
) -> TeamDetailResponse:
    """Retrieve detailed team record by unique team ID."""
    repo = TeamRepository(db)
    team = repo.get_with_relations(team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found",
        )
    return TeamDetailResponse.model_validate(team)
