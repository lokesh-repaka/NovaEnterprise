"""Research workflow and telemetry models for LangGraph multi-agent execution."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.app.models.base import Base

# Cross-dialect JSON type
JSONType = JSON().with_variant(SQLiteJSON, "sqlite")


class ResearchSession(Base):
    """Execution session for a multi-hop enterprise research query."""

    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    complexity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_questions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    evidence_data: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    execution_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    events: Mapped[list["WorkflowEvent"]] = relationship(
        "WorkflowEvent", back_populates="session", cascade="all, delete-orphan"
    )
    citations: Mapped[list["CitationRecord"]] = relationship(
        "CitationRecord", back_populates="session", cascade="all, delete-orphan"
    )


class WorkflowEvent(Base):
    """Telemetry trace event emitted during LangGraph node transitions."""

    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_name: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(64), default="node_complete", nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    session: Mapped["ResearchSession"] = relationship(
        "ResearchSession", back_populates="events"
    )


class CitationRecord(Base):
    """Verified citation pointing to retrieved evidence chunks."""

    __tablename__ = "citation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    session: Mapped["ResearchSession"] = relationship(
        "ResearchSession", back_populates="citations"
    )
