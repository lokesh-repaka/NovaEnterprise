"""Pydantic v2 schemas for research workflow lifecycle and telemetry (P10-3, P10-4, F1, F16).

Defines API contract models for:
- POST /api/v1/research request & 202 response (ResearchCreateRequest, ResearchCreateResponse)
- GET /api/v1/research session list summary (ResearchSessionSummary)
- GET /api/v1/research/{session_id} full state polling (ResearchSessionResponse)
- GET /api/v1/research/{session_id}/events telemetry trace stream (WorkflowEventResponse)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchCreateRequest(BaseModel):
    """Payload for submitting an asynchronous enterprise research query (F1)."""

    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Natural language enterprise inquiry requiring multi-hop research",
        examples=[
            "Which customers were impacted by the Payments API outage last quarter and what ADR was created to address it?"
        ],
    )
    user_id: str | None = Field(
        default=None,
        description="Optional requesting analyst identifier for episodic memory tracking",
    )


class ResearchCreateResponse(BaseModel):
    """Immediate HTTP 202 Accepted acknowledgement returned to caller (F1)."""

    session_id: str = Field(..., description="Unique research execution identifier")
    status: str = Field(
        default="running",
        description="Initial workflow execution state ('running')",
    )
    question: str = Field(..., description="Echoed research question text")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )

    model_config = ConfigDict(from_attributes=True)


class ResearchSessionSummary(BaseModel):
    """Compact summary of a research session for list endpoints."""

    session_id: str = Field(..., description="Unique research session identifier")
    status: str = Field(..., description="Current status: running, completed, failed")
    question: str = Field(..., description="Original question text")
    complexity: str | None = Field(default=None, description="Assessed complexity tier")
    execution_time_seconds: float | None = Field(
        default=None, description="Elapsed execution duration in seconds"
    )
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last state mutation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ResearchSessionResponse(BaseModel):
    """Complete research session state container for progress polling (F1, Claude.md §4.1)."""

    session_id: str = Field(..., description="Unique research session identifier")
    status: str = Field(..., description="Execution status: running, completed, failed")
    question: str = Field(..., description="Original inquiry text")
    complexity: str | None = Field(default=None, description="Assessed complexity tier")
    strategies_used: list[str] = Field(
        default_factory=list,
        description="Retrieval strategies executed (vector, sql, graph, hybrid)",
    )
    corrective_rounds: int = Field(
        default=0,
        description="Number of corrective retrieval loops executed (bounded at 1)",
    )
    verification_ratio: float = Field(
        default=0.0,
        description="Proportion of claims backed by verified evidence",
    )
    answer: str | None = Field(
        default=None,
        description="Synthesized Markdown answer text with embedded [n] citation markers",
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Array of verified citation mappings to evidence locators",
    )
    sub_questions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Decomposed sub-questions with assigned retrieval stores",
    )
    execution_time_seconds: float | None = Field(
        default=None, description="Total workflow run duration in seconds"
    )
    error_message: str | None = Field(
        default=None, description="Terminal failure or non-fatal degradation message"
    )
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last state mutation timestamp")

    model_config = ConfigDict(from_attributes=True)


class WorkflowEventResponse(BaseModel):
    """Telemetry trace event emitted during LangGraph node transitions (F16, N9)."""

    event_id: int | str = Field(..., description="Unique event identifier")
    session_id: str = Field(..., description="Parent research session ID")
    node_name: str = Field(..., description="Executing workflow node or subsystem name")
    event_type: str = Field(
        default="node_complete",
        description="Event category: node_complete, node_error, retrieval_query, decision",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized event output and decisions stripped of raw prompts (N9)",
    )
    latency_ms: int | None = Field(
        default=None, description="Node execution latency in milliseconds"
    )
    timestamp: datetime = Field(
        ..., description="UTC timestamp of the transition event"
    )

    model_config = ConfigDict(from_attributes=True)
