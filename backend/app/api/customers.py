"""Customer domain browse API routes (P4-2).

Provides endpoints for listing, filtering, and retrieving customer enterprise accounts.
Protected by require_role("viewer") RBAC guard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.domain import CustomerRepository
from backend.app.schemas.entities import CustomerResponse

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get(
    "",
    response_model=list[CustomerResponse],
    summary="List enterprise customers",
    description="Retrieve a paginated list of enterprise customers with optional tier filtering.",
)
def list_customers(
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    tier: str | None = Query(None, description="Filter by customer tier (enterprise, standard, smb)"),
) -> list[CustomerResponse]:
    """List enterprise customer records."""
    repo = CustomerRepository(db)
    customers = repo.list_customers(skip=skip, limit=limit, tier=tier)
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
    description="Retrieve a single customer record by its identifier.",
)
def get_customer(
    customer_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerResponse:
    """Retrieve customer details by unique customer ID."""
    repo = CustomerRepository(db)
    customer = repo.get(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found",
        )
    return CustomerResponse.model_validate(customer)
