"""Platform and engineering project browse API routes (P4-3).

Provides endpoints for listing, filtering, and retrieving internal initiatives,
including tracked task tickets.
Protected by require_role("viewer") RBAC guard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.domain import ProjectRepository
from backend.app.schemas.entities import ProjectDetailResponse, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List platform projects",
    description="Retrieve a paginated list of engineering initiatives with optional status and owning team filters.",
)
def list_projects(
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by project status (active, completed, archived)",
    ),
    team_id: str | None = Query(
        None, description="Filter by owning engineering team ID"
    ),
) -> list[ProjectResponse]:
    """List project records matching criteria."""
    repo = ProjectRepository(db)
    projects = repo.list_projects(
        skip=skip,
        limit=limit,
        status=status_filter,
        team_id=team_id,
    )
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project by ID",
    description="Retrieve project details with tracked issue and task tickets.",
)
def get_project(
    project_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectDetailResponse:
    """Retrieve detailed project record by unique project ID."""
    repo = ProjectRepository(db)
    project = repo.get_with_relations(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return ProjectDetailResponse.model_validate(project)
