"""Governance and administrative approval API router (P11-2, F17, Claude.md §12, §18.1).

Implements:
- GET  /api/v1/approvals: List pending and resolved approval requests [viewer+]
- GET  /api/v1/approvals/{id}: Retrieve single approval request [viewer+]
- POST /api/v1/approvals/{id}/decide: Approve or reject destructive actions [admin only]
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from backend.app.core.logging import get_logger
from backend.app.core.security import AuthenticatedUser, Role, require_role
from backend.app.schemas.approvals import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalRequestResponse,
)
from backend.app.services.approval_service import (
    ApprovalService,
    get_approval_service,
)

logger = get_logger("api.approvals")

router = APIRouter(prefix="/approvals", tags=["Governance & Approvals"])


def _get_service() -> ApprovalService:
    """Dependency provider yielding ApprovalService singleton."""
    return get_approval_service()


@router.get(
    "",
    response_model=list[ApprovalRequestResponse],
    summary="List approval requests",
    description="Retrieve paginated list of pending and resolved administrative approval requests (F17).",
)
def list_approvals(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Optional filter by status: pending, approved, rejected",
    ),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(50, ge=1, le=100, description="Page size limit"),
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[ApprovalService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> list[ApprovalRequestResponse]:
    """List approval requests."""
    records = service.list_approvals(status=status_filter, skip=skip, limit=limit)
    return [ApprovalRequestResponse.model_validate(r) for r in records]


@router.get(
    "/{id}",
    response_model=ApprovalRequestResponse,
    summary="Retrieve single approval request",
    description="Inspect details of an administrative approval gate (F17).",
)
def get_approval(
    id: str = Path(..., description="Unique approval request identifier"),
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[ApprovalService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> ApprovalRequestResponse:
    """Retrieve single approval request by ID."""
    req = service.get_approval(id)
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{id}' not found",
        )
    return ApprovalRequestResponse.model_validate(req)


@router.post(
    "/{id}/decide",
    response_model=ApprovalDecisionResponse,
    summary="Resolve administrative approval request",
    description="Approve or reject a pending destructive action. Restricted strictly to admin role (F17, Claude.md §18.1).",
)
def decide_approval(
    request: ApprovalDecisionRequest,
    id: str = Path(..., description="Approval request identifier to resolve"),
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[ApprovalService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> ApprovalDecisionResponse:
    """Approve or reject an approval request."""
    try:
        req, execution_result = service.decide_approval(
            approval_id=id,
            decision=request.decision,
            decided_by=current_user.username,
            reason=request.reason,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ApprovalDecisionResponse(
        id=req.id,
        status=req.status,
        decided_by=req.decided_by or current_user.username,
        decided_at=datetime.now(timezone.utc),
        execution_result=execution_result,
    )
