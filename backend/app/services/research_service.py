"""Research workflow orchestration, per-node state persistence, and telemetry service (P10-2, F16, N9, Claude.md §4.1, §16).

Primary Responsibilities:
- Manage multi-agent research sessions (create, poll, list, update).
- Stream LangGraph StateGraph execution, updating database state after EVERY node transition (Claude.md §4.1).
- Emit structured telemetry records to workflow_events table (F16).
- Strictly enforce Prompt Privacy (N9): strip raw prompts and secrets before DB write.
- Persist verified citations in citation_records table.
- Zero-crash telemetry and persistence resilience: DB errors during telemetry/persist never fail active workflows.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from agents.graph import get_compiled_graph
from agents.state import ResearchState
from backend.app.core.db import get_session_factory
from backend.app.core.logging import get_logger
from backend.app.core.observability import (
    filter_telemetry_payload,
    get_tracer,
)
from backend.app.models.research import ResearchSession, WorkflowEvent
from backend.app.repositories.research import (
    CitationRecordRepository,
    ResearchSessionRepository,
    WorkflowEventRepository,
)
from rag.evidence import Evidence

logger = get_logger("services.research")


def _extract_field(
    state: ResearchState | dict[str, Any], key: str, default: Any = None
) -> Any:
    """Extract a field from either a ResearchState model or dictionary."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _serialize_evidence_item(item: Any) -> dict[str, Any]:
    """Convert an evidence record (model or dict) to a JSON-serializable dictionary."""
    if isinstance(item, Evidence):
        return item.model_dump()
    if hasattr(item, "model_dump"):
        return item.model_dump()  # type: ignore[no-any-return]
    if isinstance(item, dict):
        return dict(item)
    return {"raw": str(item)}


class ResearchService:
    """Orchestrates research sessions, StateGraph execution, state persistence, and telemetry."""

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self._session_factory = session_factory or get_session_factory()
        self._tracer = get_tracer()

    def create_session(
        self,
        question: str,
        user_id: str | None = None,
        complexity: str = "moderate",
        session_id: str | None = None,
    ) -> ResearchSession:
        """Create and persist a new research session row in 'running' state."""
        sid = session_id or f"rs-{uuid.uuid4().hex[:12]}"
        with self._session_factory() as db:
            repo = ResearchSessionRepository(db)
            session = repo.create_session(
                question=question,
                complexity=complexity,
                session_id=sid,
            )
            # Commit handled by repository create
            logger.info(
                "Created research session %s for user %s: '%s'",
                sid,
                user_id,
                question[:60],
            )
            return session

    def get_session(
        self, session_id: str, load_relations: bool = True
    ) -> ResearchSession | None:
        """Retrieve a research session by ID, optionally eager-loading citations and events."""
        with self._session_factory() as db:
            repo = ResearchSessionRepository(db)
            if load_relations:
                return repo.get_with_relations(session_id)
            return repo.get(session_id)

    def list_recent_sessions(
        self, limit: int = 50, status: str | None = None
    ) -> list[ResearchSession]:
        """List recently created research sessions, optionally filtered by status."""
        with self._session_factory() as db:
            repo = ResearchSessionRepository(db)
            return repo.list_recent(limit=limit, status=status)

    def list_events(self, session_id: str) -> list[WorkflowEvent]:
        """Retrieve all recorded workflow telemetry events for a session chronologically."""
        with self._session_factory() as db:
            repo = WorkflowEventRepository(db)
            return repo.list_by_session(session_id, order_asc=True)

    def record_node_event(
        self,
        session_id: str,
        node_name: str,
        payload: dict[str, Any] | None = None,
        event_type: str = "node_complete",
        latency_ms: int | None = None,
        db: Session | None = None,
    ) -> WorkflowEvent | None:
        """Record a telemetry event in the database with strict privacy filtering (F16, N9).

        Never raises exceptions to guarantee telemetry operations do not disrupt workflows.
        """
        clean_payload = filter_telemetry_payload(payload or {})

        def _do_record(session: Session) -> WorkflowEvent:
            repo = WorkflowEventRepository(session)
            return repo.record_event(
                session_id=session_id,
                node_name=node_name,
                event_type=event_type,
                payload=clean_payload,
                latency_ms=latency_ms,
            )

        try:
            if db is not None:
                event = _do_record(db)
            else:
                with self._session_factory() as session:
                    event = _do_record(session)

            # Also sync with in-memory tracer
            self._tracer.record_event(
                session_id=session_id,
                node_name=node_name,
                event_type=event_type,
                payload=clean_payload,
                latency_ms=latency_ms,
            )
            return event
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed recording node event for %s (session %s): %s",
                node_name,
                session_id,
                exc,
            )
            return None

    def _persist(
        self,
        session_id: str,
        state: ResearchState | dict[str, Any],
        node_name: str | None = None,
        db: Session | None = None,
    ) -> None:
        """Update research_sessions row with latest state snapshot after a node transition.

        Claude.md §4.1: "The state in the database is the progress bar."
        Telemetry/persistence errors are caught and logged; never crash active runs.
        """
        status = str(_extract_field(state, "status", "running"))
        complexity = _extract_field(state, "complexity")
        answer = _extract_field(state, "answer")
        sub_questions_raw = _extract_field(state, "sub_questions", []) or []
        evidence_raw = _extract_field(state, "evidence", []) or []
        execution_time = _extract_field(state, "execution_time_seconds")
        citations_raw = _extract_field(state, "citations", []) or []

        # Serialize sub_questions safely
        sub_questions: list[dict[str, Any]] = []
        for sq in sub_questions_raw:
            if isinstance(sq, dict):
                sub_questions.append(dict(sq))
            elif hasattr(sq, "model_dump"):
                sub_questions.append(sq.model_dump())

        # Serialize evidence data safely
        evidence_data: list[dict[str, Any]] = [
            _serialize_evidence_item(e) for e in evidence_raw
        ]

        def _do_persist(session: Session) -> None:
            repo = ResearchSessionRepository(session)
            session_row = repo.get(session_id)
            if session_row is None:
                logger.warning(
                    "Research session %s not found for persistence", session_id
                )
                return

            session_row.status = status
            if complexity:
                session_row.complexity = str(complexity)
            if answer is not None:
                session_row.answer = str(answer)
            if sub_questions:
                session_row.sub_questions = sub_questions
            if evidence_data:
                session_row.evidence_data = evidence_data
            if execution_time is not None:
                session_row.execution_time = float(execution_time)
            session_row.updated_at = datetime.now(timezone.utc)

            session.commit()

            # If citations are present and workflow is concluding or at verification, persist citations
            if citations_raw and (
                node_name in {"update_memory", "verify_citations"}
                or status == "completed"
            ):
                cit_repo = CitationRecordRepository(session)
                existing_cits = {
                    c.locator for c in cit_repo.list_by_session(session_id) if c.locator
                }
                for c in citations_raw:
                    c_dict = (
                        c
                        if isinstance(c, dict)
                        else (c.model_dump() if hasattr(c, "model_dump") else {})
                    )
                    locator = c_dict.get("locator")
                    if locator and locator not in existing_cits:
                        cit_repo.record_citation(
                            session_id=session_id,
                            chunk_id=c_dict.get("chunk_id"),
                            document_id=c_dict.get("document_id"),
                            locator=locator,
                            text_snippet=c_dict.get("snippet"),
                            score=c_dict.get("score"),
                        )
                        existing_cits.add(locator)

        try:
            if db is not None:
                _do_persist(db)
            else:
                with self._session_factory() as session:
                    _do_persist(session)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed persisting research state for session %s (node=%s): %s",
                session_id,
                node_name,
                exc,
            )

    def run_research(
        self,
        session_id: str,
        question: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute compiled LangGraph StateGraph, streaming updates and persisting state after every node."""
        logger.info(
            "Starting research execution for session %s (user: %s)",
            session_id,
            user_id,
        )
        start_time = time.perf_counter()

        initial_payload: dict[str, Any] = {
            "session_id": session_id,
            "question": question,
            "user_id": user_id,
            "status": "running",
        }

        # Initial progress persistence
        self._persist(session_id, initial_payload, node_name="start")

        accumulated_state: dict[str, Any] = dict(initial_payload)
        compiled_graph = get_compiled_graph()

        try:
            step_start = time.perf_counter()
            for step_chunk in compiled_graph.stream(
                initial_payload, stream_mode="updates"
            ):
                for node_name, partial_update in step_chunk.items():
                    elapsed_ms = int((time.perf_counter() - step_start) * 1000)
                    step_start = time.perf_counter()

                    if isinstance(partial_update, dict):
                        accumulated_state.update(partial_update)
                    elif hasattr(partial_update, "model_dump"):
                        accumulated_state.update(partial_update.model_dump())

                    # Persist state after each node transition (Claude.md §4.1)
                    self._persist(session_id, accumulated_state, node_name=node_name)

                    # Record node transition event in workflow_events (F16)
                    self.record_node_event(
                        session_id=session_id,
                        node_name=node_name,
                        payload=partial_update
                        if isinstance(partial_update, dict)
                        else {},
                        event_type="node_complete",
                        latency_ms=elapsed_ms,
                    )

            total_elapsed = round(time.perf_counter() - start_time, 2)
            accumulated_state["execution_time_seconds"] = total_elapsed
            accumulated_state["status"] = "completed"

            # Final persistence to ensure completed state and citations are recorded
            self._persist(session_id, accumulated_state, node_name="update_memory")
            logger.info(
                "Completed research execution for session %s in %.2fs",
                session_id,
                total_elapsed,
            )
            return accumulated_state

        except Exception as exc:
            total_elapsed = round(time.perf_counter() - start_time, 2)
            logger.exception(
                "Research execution failed for session %s after %.2fs",
                session_id,
                total_elapsed,
            )
            accumulated_state["status"] = "failed"
            accumulated_state["execution_time_seconds"] = total_elapsed
            err_msg = str(exc)
            errs = list(accumulated_state.get("errors", []))
            errs.append(err_msg)
            accumulated_state["errors"] = errs

            self._persist(session_id, accumulated_state, node_name="error")
            self.record_node_event(
                session_id=session_id,
                node_name="workflow_error",
                payload={
                    "error_type": exc.__class__.__name__,
                    "error_message": err_msg,
                },
                event_type="node_error",
                latency_ms=int(total_elapsed * 1000),
            )
            raise

    # Alias per docs/02-hld.md:135
    start_research = run_research


# Singleton service instance
_research_service_instance: ResearchService | None = None


def get_research_service(
    session_factory: sessionmaker[Session] | None = None,
) -> ResearchService:
    """Retrieve or initialize the ResearchService singleton."""
    global _research_service_instance
    if _research_service_instance is None or session_factory is not None:
        _research_service_instance = ResearchService(session_factory=session_factory)
    return _research_service_instance


def reset_research_service() -> None:
    """Reset the ResearchService singleton (used between test fixtures)."""
    global _research_service_instance
    _research_service_instance = None


__all__ = [
    "ResearchService",
    "get_research_service",
    "reset_research_service",
]
