"""Observability tracer and telemetry event recorder for NovaEnterprise (Claude.md §16, PRD §F16, §N9).

Provides:
- Telemetry trace recorder tracking node transitions, queries, tool calls, and decisions (F16)
- tracer.node(...) context manager measuring execution latency in milliseconds
- Strict Prompt Privacy (N9): filters out internal prompts, chain-of-thought, and secrets
- Resilient failure handling: telemetry operations never raise or disrupt workflow runs
- Dual in-memory and relational database persistence (workflow_events table)
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.logging import get_logger
from backend.app.core.upload_validator import scrub_secrets

logger = get_logger("core.observability")

# Keys prohibited from being exposed in public telemetry to preserve prompt privacy (N9)
DISALLOWED_PROMPT_KEYS: set[str] = {
    "prompt",
    "system_prompt",
    "raw_prompt",
    "internal_prompt",
    "messages",
    "thought",
    "thoughts",
    "chain_of_thought",
    "internal_reasoning",
    "reasoning_content",
    "cot",
    "credentials",
    "password",
    "api_key",
    "secret",
    "auth_token",
}


class TelemetryEvent(BaseModel):
    """Structured telemetry event model for workflow execution (F16)."""

    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid4().hex[:12]}",
        description="Unique identifier for the telemetry event",
    )
    session_id: str = Field(..., description="Correlated research session ID")
    node_name: str = Field(
        ..., description="Name of the executing workflow node or tool"
    )
    event_type: str = Field(
        default="node_complete",
        description="Type of event: node_start, node_complete, node_error, retrieval_query, decision, tool_call",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized event payload stripped of raw prompts and secrets (N9)",
    )
    latency_ms: int | None = Field(
        default=None,
        description="Elapsed execution time in milliseconds",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the telemetry event",
    )


def filter_telemetry_payload(data: Any) -> Any:
    """Recursively scrub raw prompts, chain-of-thought, and secrets from telemetry (N9).

    Guarantees:
    - Serializes Pydantic models to dicts for JSON safety.
    - Strips internal system prompts and chain-of-thought tokens.
    - Scrubs embedded secrets and credentials in text values.
    - Preserves operational metrics, decisions, query summaries, and locators.
    """
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif hasattr(data, "dict") and callable(data.dict):
        data = data.dict()

    if isinstance(data, dict):
        clean_dict: dict[str, Any] = {}
        for key, val in data.items():
            if str(key).lower() in DISALLOWED_PROMPT_KEYS:
                continue
            clean_dict[key] = filter_telemetry_payload(val)
        return clean_dict
    elif isinstance(data, list):
        return [filter_telemetry_payload(item) for item in data]
    elif isinstance(data, str):
        # Scrub embedded secrets (AWS keys, passwords, API keys) from string payload values
        scrub_res = scrub_secrets(data)
        return scrub_res.scrubbed_text
    else:
        return data


class NodeExecutionContext:
    """Context tracker inside a tracer.node(...) block."""

    def __init__(self, node_name: str, session_id: str) -> None:
        self.node_name = node_name
        self.session_id = session_id
        self.start_time: float = time.perf_counter()
        self.payload: dict[str, Any] = {}

    def set_payload(self, payload: dict[str, Any]) -> None:
        """Assign output payload for the executing node."""
        if isinstance(payload, dict):
            self.payload = dict(payload)

    def add_payload(self, key: str, value: Any) -> None:
        """Append or update a key in the node output payload."""
        self.payload[key] = value


class ObservabilityTracer:
    """Thread-safe event tracer for LangGraph nodes and retrieval executions (F16, N9)."""

    def __init__(self) -> None:
        self._events: dict[str, list[TelemetryEvent]] = {}
        self._lock = threading.Lock()

    def record_event(
        self,
        session_id: str,
        node_name: str,
        event_type: str = "node_complete",
        payload: dict[str, Any] | None = None,
        latency_ms: int | None = None,
        db: Any | None = None,
    ) -> TelemetryEvent:
        """Record a telemetry event in memory and optionally persist to workflow_events.

        Telemetry operations never raise exceptions to avoid breaking active runs (Claude.md §16).
        """
        try:
            clean_payload = filter_telemetry_payload(payload or {})
            event = TelemetryEvent(
                session_id=session_id,
                node_name=node_name,
                event_type=event_type,
                payload=clean_payload,
                latency_ms=latency_ms,
            )

            # 1. Thread-safe in-memory recording
            with self._lock:
                if session_id not in self._events:
                    self._events[session_id] = []
                self._events[session_id].append(event)

            # 2. Database persistence (if DB session provided)
            if db is not None:
                self._persist_to_db(db, event)

            return event
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Telemetry record failed for node '%s' (session=%s): %s",
                node_name,
                session_id,
                exc,
            )
            # Return fallback event so caller has a reference
            return TelemetryEvent(
                session_id=session_id,
                node_name=node_name,
                event_type=event_type,
                payload={"telemetry_error": "Record failed gracefully"},
                latency_ms=latency_ms,
            )

    def _persist_to_db(self, db: Any, event: TelemetryEvent) -> None:
        """Persist a telemetry event to the workflow_events database table."""
        try:
            from backend.app.models.research import WorkflowEvent

            db_evt = WorkflowEvent(
                session_id=event.session_id,
                node_name=event.node_name,
                event_type=event.event_type,
                payload=event.payload,
                latency_ms=event.latency_ms,
                timestamp=event.timestamp,
            )
            db.add(db_evt)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to persist workflow_event to database (session=%s): %s",
                event.session_id,
                exc,
            )
            try:
                db.rollback()
            except Exception:  # noqa: BLE001, S110
                pass

    @contextmanager
    def node(
        self,
        session_id: str,
        node_name: str,
        db: Any | None = None,
    ) -> Generator[NodeExecutionContext, None, None]:
        """Context manager wrapping node execution to measure latency and record completion."""
        ctx = NodeExecutionContext(node_name=node_name, session_id=session_id)
        try:
            yield ctx
            # Execution succeeded
            elapsed_ms = int((time.perf_counter() - ctx.start_time) * 1000)
            self.record_event(
                session_id=session_id,
                node_name=node_name,
                event_type="node_complete",
                payload=ctx.payload,
                latency_ms=elapsed_ms,
                db=db,
            )
        except Exception as exc:
            # Execution failed with error
            elapsed_ms = int((time.perf_counter() - ctx.start_time) * 1000)
            error_payload = {
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                **filter_telemetry_payload(ctx.payload),
            }
            self.record_event(
                session_id=session_id,
                node_name=node_name,
                event_type="node_error",
                payload=error_payload,
                latency_ms=elapsed_ms,
                db=db,
            )
            # Re-raise user exception so workflow can handle error
            raise

    def record_query(
        self,
        session_id: str,
        store_type: str,
        query_text: str,
        result_count: int = 0,
        latency_ms: int | None = None,
        db: Any | None = None,
    ) -> TelemetryEvent:
        """Record retrieval query execution (SQL, Cypher, or Vector)."""
        payload = {
            "store_type": store_type,
            "query": query_text,
            "result_count": result_count,
        }
        return self.record_event(
            session_id=session_id,
            node_name=f"{store_type}_retrieval",
            event_type="retrieval_query",
            payload=payload,
            latency_ms=latency_ms,
            db=db,
        )

    def record_decision(
        self,
        session_id: str,
        decision_type: str,
        choice: str,
        rationale: str = "",
        rule_applied: str | None = None,
        db: Any | None = None,
    ) -> TelemetryEvent:
        """Record an architectural or routing decision."""
        payload = {
            "decision_type": decision_type,
            "choice": choice,
            "rationale": rationale,
            "rule_applied": rule_applied,
        }
        return self.record_event(
            session_id=session_id,
            node_name="decision_gate",
            event_type="decision",
            payload=payload,
            db=db,
        )

    def record_tool_call(
        self,
        session_id: str,
        tool_name: str,
        input_args: dict[str, Any] | None = None,
        output_summary: Any = None,
        latency_ms: int | None = None,
        db: Any | None = None,
    ) -> TelemetryEvent:
        """Record a tool execution event."""
        payload = {
            "tool_name": tool_name,
            "input_args": filter_telemetry_payload(input_args or {}),
            "output_summary": filter_telemetry_payload(output_summary),
            "latency_ms": latency_ms,
        }
        return self.record_event(
            session_id=session_id,
            node_name=tool_name,
            event_type="tool_call",
            payload=payload,
            latency_ms=latency_ms,
            db=db,
        )

    def get_events(self, session_id: str) -> list[TelemetryEvent]:
        """Retrieve all recorded telemetry events for a session in chronological order."""
        with self._lock:
            return list(self._events.get(session_id, []))

    def clear_session(self, session_id: str) -> None:
        """Remove recorded in-memory telemetry events for a specific session."""
        with self._lock:
            self._events.pop(session_id, None)


# Global singleton instance
_tracer_instance: ObservabilityTracer | None = None
_instance_lock = threading.Lock()


def get_tracer() -> ObservabilityTracer:
    """Retrieve the application-wide ObservabilityTracer singleton."""
    global _tracer_instance
    if _tracer_instance is None:
        with _instance_lock:
            if _tracer_instance is None:
                _tracer_instance = ObservabilityTracer()
    return _tracer_instance


# Export module-level tracer instance
tracer: ObservabilityTracer = get_tracer()
