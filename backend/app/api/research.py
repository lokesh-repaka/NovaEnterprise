"""Research execution, session status polling, and telemetry API router (P10-3, P10-4, F1, F16).

Implements:
- POST /api/v1/research: Launch asynchronous research workflow with BackgroundTasks returning 202 Accepted (F1).
- GET  /api/v1/research: List recent research sessions with status summaries.
- GET  /api/v1/research/{session_id}: Poll current session state, answer, citations, and progress bar (Claude.md §4.1).
- GET  /api/v1/research/{session_id}/events: Inspect node transitions, queries, latencies, and decisions (F16, N9).
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.app.core.logging import get_logger
from backend.app.core.security import AuthenticatedUser, Role, require_role
from backend.app.schemas.research import (
    ResearchCreateRequest,
    ResearchCreateResponse,
    ResearchSessionResponse,
    ResearchSessionSummary,
    WorkflowEventResponse,
)
from backend.app.services.research_service import (
    ResearchService,
    get_research_service,
)

logger = get_logger("api.research")

router = APIRouter(prefix="/research", tags=["Research & Observability"])


def _get_service() -> ResearchService:
    """Dependency provider yielding the ResearchService singleton."""
    return get_research_service()


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ResearchCreateResponse,
    summary="Launch asynchronous enterprise research query",
    description="Initializes a research session row and schedules background LangGraph StateGraph execution (F1).",
)
def create_research_session(
    request: ResearchCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_role(Role.ANALYST, Role.ADMIN))
    ],
    service: Annotated[ResearchService, Depends(_get_service)],
) -> ResearchCreateResponse:
    """Accept natural language inquiry, initialize session, and dispatch background workflow."""
    user_id = request.user_id or current_user.username
    session = service.create_session(
        question=request.question,
        user_id=user_id,
    )

    logger.info(
        "Scheduled background research for session %s (user: %s)",
        session.id,
        user_id,
    )
    # Schedule background execution of the compiled 13-node StateGraph
    background_tasks.add_task(
        service.run_research,
        session.id,
        request.question,
        user_id,
    )

    return ResearchCreateResponse(
        session_id=session.id,
        status=session.status,
        question=session.question,
        created_at=session.created_at,
    )


@router.get(
    "",
    response_model=list[ResearchSessionSummary],
    summary="List recent research sessions",
    description="Retrieve recent research executions with status and timing metadata.",
)
def list_research_sessions(
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(20, ge=1, le=100, description="Page size limit"),
    status: str | None = Query(
        None, description="Optional status filter: running, completed, failed"
    ),
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[ResearchService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> list[ResearchSessionSummary]:
    """Retrieve list of research sessions with status summaries."""
    sessions = service.list_recent_sessions(limit=limit + skip, status=status)
    page = sessions[skip : skip + limit]
    return [
        ResearchSessionSummary(
            session_id=s.id,
            status=s.status,
            question=s.question,
            complexity=s.complexity,
            execution_time_seconds=s.execution_time,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in page
    ]


@router.get(
    "/{session_id}",
    response_model=ResearchSessionResponse,
    summary="Poll research session state and answer",
    description="Poll current progress, synthesized answer, evidence, and citations (Claude.md §4.1).",
)
def get_research_session(
    session_id: str,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[ResearchService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> ResearchSessionResponse:
    """Retrieve full research session state for progress polling."""
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research session '{session_id}' not found",
        )

    # Format citations from relationship records or session payload
    citations = [
        {
            "citation_id": idx + 1,
            "id": c.id,
            "locator": c.locator,
            "document_id": c.document_id,
            "chunk_id": c.chunk_id,
            "snippet": c.text_snippet,
            "score": c.score,
        }
        for idx, c in enumerate(session.citations or [])
    ]

    # Collect unique strategies used from sub_questions
    strategies_used: list[str] = []
    for sq in session.sub_questions or []:
        st = sq.get("strategy")
        if st and st not in strategies_used:
            strategies_used.append(st)

    # Collect corrective rounds and verification ratio from events
    corrective_rounds = 0
    verification_ratio = 1.0 if session.status == "completed" else 0.0
    for e in session.events or []:
        if e.node_name == "corrective_retrieval":
            corrective_rounds += 1
        if e.node_name == "verify_evidence" and e.payload:
            vr = e.payload.get("verification_ratio")
            if isinstance(vr, (int, float)):
                verification_ratio = float(vr)

    return ResearchSessionResponse(
        session_id=session.id,
        status=session.status,
        question=session.question,
        complexity=session.complexity,
        strategies_used=strategies_used,
        corrective_rounds=corrective_rounds,
        verification_ratio=verification_ratio,
        answer=session.answer,
        citations=citations,
        sub_questions=session.sub_questions or [],
        execution_time_seconds=session.execution_time,
        error_message=None,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get(
    "/{session_id}/events",
    response_model=list[WorkflowEventResponse],
    summary="Inspect workflow telemetry trace events",
    description="Timeline of node transitions, queries, latencies, and decisions (F16, N9).",
)
def get_research_session_events(
    session_id: str,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[ResearchService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> list[WorkflowEventResponse]:
    """Retrieve sanitized execution telemetry stream for a session."""
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research session '{session_id}' not found",
        )

    events = service.list_events(session_id)
    return [
        WorkflowEventResponse(
            event_id=e.id,
            session_id=e.session_id,
            node_name=e.node_name,
            event_type=e.event_type,
            payload=e.payload or {},
            latency_ms=e.latency_ms,
            timestamp=e.timestamp,
        )
        for e in events
    ]


@router.get(
    "/{session_id}/stream",
    summary="Stream live workflow telemetry events via SSE",
    description="Streams real-time or historical node transition events as Server-Sent Events (text/event-stream).",
)
def stream_research_events(
    session_id: str,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_role(Role.VIEWER, Role.ANALYST, Role.ADMIN)),
    ] = None,  # type: ignore[assignment]
    service: Annotated[ResearchService, Depends(_get_service)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """Stream telemetry events using Server-Sent Events (text/event-stream)."""
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research session '{session_id}' not found",
        )

    def event_generator() -> Any:
        events = service.list_events(session_id)
        for e in events:
            event_data = {
                "event_id": e.id,
                "session_id": e.session_id,
                "node_name": e.node_name,
                "event_type": e.event_type,
                "payload": e.payload or {},
                "latency_ms": e.latency_ms,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            yield f"event: {e.event_type or 'workflow_event'}\ndata: {json.dumps(event_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
