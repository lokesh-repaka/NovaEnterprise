"""Pydantic v2 schemas for Governance & Approval workflows (P11-2, F17, Claude.md §12, §18.1).

Defines API contract models for:
- DELETE /api/v1/documents/{id} pending approval interception (DocumentDeletePendingResponse)
- GET /api/v1/approvals & GET /api/v1/approvals/{id} (ApprovalRequestResponse)
- POST /api/v1/approvals/{id}/decide (ApprovalDecisionRequest, ApprovalDecisionResponse)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentDeletePendingResponse(BaseModel):
    """Response returned when an analyst requests document deletion (202 Accepted)."""

    message: str = Field(
        default="Deletion request queued for administrative approval",
        description="Informative message indicating request interception",
    )
    approval_request_id: str = Field(
        ..., description="Unique approval request identifier"
    )
    status: str = Field(
        default="pending_approval",
        description="Interception status ('pending_approval')",
    )


class DocumentDeleteExecutedResponse(BaseModel):
    """Response returned when an admin directly executes document deletion (200 OK)."""

    message: str = Field(..., description="Confirmation of immediate deletion")
    deleted_document_id: str = Field(..., description="ID of deleted document")
    status: str = Field(default="deleted", description="Result status ('deleted')")
    pruned_chunks: int = Field(default=0, description="Count of semantic chunks pruned")


class ApprovalRequestResponse(BaseModel):
    """Representation of an administrative approval request."""

    id: str = Field(..., description="Unique approval request identifier")
    resource_type: str = Field(
        ..., description="Target resource classification (e.g. document)"
    )
    resource_id: str = Field(..., description="Unique target resource identifier")
    action: str = Field(default="delete", description="Proposed destructive operation")
    requester_id: str = Field(
        ..., description="User ID or username who initiated the request"
    )
    status: str = Field(
        default="pending",
        description="Approval state: 'pending', 'approved', or 'rejected'",
    )
    decided_by: str | None = Field(
        default=None, description="Admin username who resolved the request"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when approval request was filed"
    )

    model_config = ConfigDict(from_attributes=True)


class ApprovalDecisionRequest(BaseModel):
    """Payload for resolving an administrative approval request."""

    decision: str = Field(
        ...,
        pattern="^(approved|rejected)$",
        description="Administrative decision: 'approved' or 'rejected'",
    )
    reason: str | None = Field(
        default=None,
        description="Optional justification or audit notes for the decision",
    )


class ApprovalDecisionResponse(BaseModel):
    """Response returned upon resolving an approval request."""

    id: str = Field(..., description="Unique approval request identifier")
    status: str = Field(..., description="Resulting status: 'approved' or 'rejected'")
    decided_by: str = Field(..., description="Admin username who made the decision")
    decided_at: datetime = Field(..., description="UTC resolution timestamp")
    execution_result: dict[str, Any] | None = Field(
        default=None,
        description="Output metadata from executing approved action (or rejection note)",
    )

    model_config = ConfigDict(from_attributes=True)
