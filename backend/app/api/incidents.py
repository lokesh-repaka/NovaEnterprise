"""Incident domain browse API routes (P4-2).

Provides endpoints for listing, filtering, and retrieving production and security incidents.
Protected by require_role("viewer") RBAC guard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.domain import IncidentRepository
from backend.app.schemas.entities import IncidentDetailResponse, IncidentResponse

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get(
    "",
    response_model=list[IncidentResponse],
    summary="List production incidents",
    description="Retrieve a paginated list of production incidents with optional severity, status, and service filters.",
)
def list_incidents(
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    severity: str | None = Query(
        None, description="Filter by severity level (SEV1, SEV2, SEV3)"
    ),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by incident status (investigating, mitigated, resolved)",
    ),
    service_id: str | None = Query(None, description="Filter by impacted service ID"),
) -> list[IncidentResponse]:
    """List incident records matching criteria."""
    repo = IncidentRepository(db)
    incidents = repo.list_incidents(
        skip=skip,
        limit=limit,
        severity=severity,
        status=status_filter,
        service_id=service_id,
    )
    return [IncidentResponse.model_validate(inc) for inc in incidents]


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Get incident by ID",
    description="Retrieve incident details including impacted service and associated ADR decisions.",
)
def get_incident(
    incident_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
) -> IncidentDetailResponse:
    """Retrieve detailed incident record by ID."""
    repo = IncidentRepository(db)
    incident = repo.get_with_relations(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return IncidentDetailResponse.model_validate(incident)
