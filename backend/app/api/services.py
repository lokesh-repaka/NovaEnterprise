"""Service domain browse API routes (P4-2).

Provides endpoints for listing, filtering, and retrieving microservices and catalog components.
Protected by require_role("viewer") RBAC guard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.domain import ServiceRepository
from backend.app.schemas.entities import ServiceResponse

router = APIRouter(prefix="/services", tags=["services"])


@router.get(
    "",
    response_model=list[ServiceResponse],
    summary="List catalog services",
    description="Retrieve a paginated list of catalog microservices with optional tier and team filters.",
)
def list_services(
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    tier: str | None = Query(None, description="Filter by service tier (tier-1, tier-2)"),
    owner_team_id: str | None = Query(None, description="Filter by owning team identifier"),
) -> list[ServiceResponse]:
    """List service catalog records matching criteria."""
    repo = ServiceRepository(db)
    services = repo.list_services(skip=skip, limit=limit, tier=tier, owner_team_id=owner_team_id)
    return [ServiceResponse.model_validate(s) for s in services]


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Get service by ID",
    description="Retrieve service metadata and owner information by service identifier.",
)
def get_service(
    service_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
) -> ServiceResponse:
    """Retrieve service details by unique service ID."""
    repo = ServiceRepository(db)
    service = repo.get(service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found",
        )
    return ServiceResponse.model_validate(service)
