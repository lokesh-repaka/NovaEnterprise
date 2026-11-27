"""Research session, workflow telemetry, and citation repositories."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.research import CitationRecord, ResearchSession, WorkflowEvent
from backend.app.repositories.base import BaseRepository


class ResearchSessionRepository(BaseRepository[ResearchSession]):
    """Repository for managing multi-agent Research Sessions."""

    def __init__(self, db: Session) -> None:
        super().__init__(ResearchSession, db)

    def create_session(
        self,
        question: str,
        complexity: str = "moderate",
        session_id: str | None = None,
    ) -> ResearchSession:
        """Create and initialize a new research session."""
        session = ResearchSession(
            id=session_id or f"rs-{uuid.uuid4().hex[:12]}",
            question=question,
            complexity=complexity,
            status="running",
        )
        return self.create(session)

    def update_status(
        self,
        session_id: str,
        status: str,
        answer: str | None = None,
        execution_time: float | None = None,
    ) -> ResearchSession | None:
        """Update session state, recording answers and execution timings."""
        session = self.get(session_id)
        if session is None:
            return None

        session.status = status
        if answer is not None:
            session.answer = answer
        if execution_time is not None:
            session.execution_time = execution_time

        return self.update(session)

    def list_active(self) -> list[ResearchSession]:
        """List active sessions currently in running or pending state."""
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.status.in_(["running", "pending"]))
            .order_by(ResearchSession.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_with_relations(self, session_id: str) -> ResearchSession | None:
        """Fetch session with citations and events eagerly loaded."""
        stmt = (
            select(ResearchSession)
            .options(
                selectinload(ResearchSession.citations),
                selectinload(ResearchSession.events),
            )
            .where(ResearchSession.id == session_id)
        )
        return self.db.scalars(stmt).first()

    def list_recent(
        self, limit: int = 50, status: str | None = None
    ) -> list[ResearchSession]:
        """List recent sessions ordered by creation time, optionally filtered by status."""
        stmt = select(ResearchSession)
        if status:
            stmt = stmt.where(ResearchSession.status == status)
        stmt = stmt.order_by(ResearchSession.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())


class WorkflowEventRepository(BaseRepository[WorkflowEvent]):
    """Repository for recording telemetry events throughout the 13 LangGraph workflow nodes."""

    def __init__(self, db: Session) -> None:
        super().__init__(WorkflowEvent, db)

    def record_event(
        self,
        session_id: str,
        node_name: str,
        event_type: str = "node_complete",
        payload: dict[str, Any] | None = None,
        latency_ms: int | None = None,
    ) -> WorkflowEvent:
        """Record a single node execution telemetry event."""
        event = WorkflowEvent(
            session_id=session_id,
            node_name=node_name,
            event_type=event_type,
            payload=payload or {},
            latency_ms=latency_ms,
        )
        return self.create(event)

    def list_by_session(
        self, session_id: str, order_asc: bool = True
    ) -> list[WorkflowEvent]:
        """Retrieve all events emitted during a specific research session."""
        stmt = select(WorkflowEvent).where(WorkflowEvent.session_id == session_id)
        if order_asc:
            stmt = stmt.order_by(WorkflowEvent.timestamp.asc(), WorkflowEvent.id.asc())
        else:
            stmt = stmt.order_by(
                WorkflowEvent.timestamp.desc(), WorkflowEvent.id.desc()
            )
        return list(self.db.scalars(stmt).all())

    def count_by_session(self, session_id: str) -> int:
        """Count total events for a research session."""
        stmt = (
            select(func.count())
            .select_from(WorkflowEvent)
            .where(WorkflowEvent.session_id == session_id)
        )
        return int(self.db.scalar(stmt) or 0)


class CitationRecordRepository(BaseRepository[CitationRecord]):
    """Repository for managing source grounding and citation resolution records."""

    def __init__(self, db: Session) -> None:
        super().__init__(CitationRecord, db)

    def record_citation(
        self,
        session_id: str,
        chunk_id: str | None = None,
        document_id: str | None = None,
        locator: str | None = None,
        text_snippet: str | None = None,
        score: float | None = None,
    ) -> CitationRecord:
        """Persist a single resolved citation for a research session."""
        citation = CitationRecord(
            session_id=session_id,
            chunk_id=chunk_id,
            document_id=document_id,
            locator=locator,
            text_snippet=text_snippet,
            score=score,
        )
        return self.create(citation)

    def list_by_session(self, session_id: str) -> list[CitationRecord]:
        """List all citations recorded for a session ordered by creation time."""
        stmt = (
            select(CitationRecord)
            .where(CitationRecord.session_id == session_id)
            .order_by(CitationRecord.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
