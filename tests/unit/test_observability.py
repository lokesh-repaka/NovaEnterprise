"""Unit tests for workflow observability tracer and telemetry privacy (P7-4, F16, N9, Claude.md §16).

Validates:
- Every node transition and query timing recorded as a TelemetryEvent (F16)
- tracer.node(...) context manager measuring latency_ms and capturing output
- Prompt privacy (N9): raw prompts, system instructions, and chain-of-thought are stripped
- Secret scrubbing inside telemetry payloads
- Telemetry never raises or crashes the workflow on failure
- Database persistence to workflow_events table when session provided
- Specialized event recorders (queries, decisions, tool calls)
"""

import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.core.observability import (
    ObservabilityTracer,
    TelemetryEvent,
    filter_telemetry_payload,
    get_tracer,
)
from backend.app.models.research import ResearchSession, WorkflowEvent


@pytest.fixture
def db_session():
    """Create a fresh in-memory SQLite session with initialized schema."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        yield session


@pytest.fixture
def clean_tracer() -> ObservabilityTracer:
    """Provide a fresh, isolated ObservabilityTracer instance."""
    return ObservabilityTracer()


def test_record_event_basic_and_event_shape(clean_tracer: ObservabilityTracer) -> None:
    """F16: Verify basic event recording produces valid TelemetryEvent models with required fields."""
    session_id = "sess-obs-101"
    evt: TelemetryEvent = clean_tracer.record_event(
        session_id=session_id,
        node_name="assess_complexity",
        event_type="node_complete",
        payload={"complexity": "complex", "rule_applied": "RULE_CROSS_DOMAIN_JOIN"},
        latency_ms=142,
    )

    assert isinstance(evt, TelemetryEvent)
    assert evt.session_id == session_id
    assert evt.node_name == "assess_complexity"
    assert evt.event_type == "node_complete"
    assert evt.payload["complexity"] == "complex"
    assert evt.payload["rule_applied"] == "RULE_CROSS_DOMAIN_JOIN"
    assert evt.latency_ms == 142
    assert evt.timestamp is not None
    assert evt.event_id.startswith("evt_")

    # Verify retrieval by session_id
    session_events = clean_tracer.get_events(session_id)
    assert len(session_events) == 1
    assert session_events[0] == evt


def test_node_context_manager_measures_latency_and_emits_complete(
    clean_tracer: ObservabilityTracer,
) -> None:
    """F16: Verify tracer.node(...) context manager measures elapsed latency and emits node_complete."""
    session_id = "sess-obs-ctx"
    with clean_tracer.node(session_id, "decompose") as ctx:
        time.sleep(0.02)  # Simulate 20ms of execution
        ctx.set_payload(
            {
                "sub_questions_count": 4,
                "strategies": ["graph", "sql", "graph", "hybrid"],
            }
        )

    events = clean_tracer.get_events(session_id)
    assert len(events) >= 1

    complete_evt = events[-1]
    assert complete_evt.node_name == "decompose"
    assert complete_evt.event_type == "node_complete"
    assert complete_evt.latency_ms is not None
    assert complete_evt.latency_ms >= 15  # At least ~15-20ms
    assert complete_evt.payload["sub_questions_count"] == 4
    assert complete_evt.payload["strategies"] == ["graph", "sql", "graph", "hybrid"]


def test_node_context_manager_handles_error_without_swallowing_user_exception(
    clean_tracer: ObservabilityTracer,
) -> None:
    """F16: Verify node errors emit node_error event and propagate exception to caller."""
    session_id = "sess-obs-err"

    with (
        pytest.raises(ValueError, match="Database connection timeout"),
        clean_tracer.node(session_id, "execute_retrieval") as ctx,
    ):
        ctx.set_payload({"store": "sql"})
        raise ValueError("Database connection timeout")

    events = clean_tracer.get_events(session_id)
    assert len(events) >= 1
    err_evt = events[-1]
    assert err_evt.node_name == "execute_retrieval"
    assert err_evt.event_type == "node_error"
    assert err_evt.payload["error_type"] == "ValueError"
    assert "Database connection timeout" in err_evt.payload["error_message"]


def test_prompt_privacy_filter_strips_internal_prompts_and_cot_n9() -> None:
    """N9: Verify prompt privacy filter strips raw prompts, system messages, and chain-of-thought."""
    raw_payload: dict[str, Any] = {
        "complexity": "complex",
        "rule_applied": "RULE_CANONICAL_QUERY",
        "system_prompt": "You are NovaEnterprise master assistant with secret directives...",
        "raw_prompt": "User asked: Which customers were impacted...",
        "thought": "Thinking process: Step 1 examine services, Step 2 query database...",
        "chain_of_thought": "Hidden internal chain of reasoning...",
        "internal_reasoning": "Model private reflection...",
        "nested": {
            "prompt": "Inner prompt template text",
            "reasoning_content": "DeepSeek R1 internal thought tokens",
            "visible_answer": "Public answer summary",
        },
    }

    sanitized = filter_telemetry_payload(raw_payload)

    # Exposed operational keys must be preserved
    assert sanitized["complexity"] == "complex"
    assert sanitized["rule_applied"] == "RULE_CANONICAL_QUERY"
    assert sanitized["nested"]["visible_answer"] == "Public answer summary"

    # Internal reasoning and prompts must be strictly stripped (N9)
    assert "system_prompt" not in sanitized
    assert "raw_prompt" not in sanitized
    assert "thought" not in sanitized
    assert "chain_of_thought" not in sanitized
    assert "internal_reasoning" not in sanitized
    assert "prompt" not in sanitized["nested"]
    assert "reasoning_content" not in sanitized["nested"]


def test_prompt_privacy_filter_scrubs_secrets_in_payload_values() -> None:
    """N9, BRD §242: Verify embedded secrets in telemetry payload strings are scrubbed."""
    fake_api_key = "sk_" + "live_" + "9876543210abcdef9876543210"
    payload = {
        "query_sql": f"SELECT * FROM api_tokens WHERE key = '{fake_api_key}'",
        "aws_meta": "Created resource using AKIAIOSFODNN7EXAMPLE",
    }

    sanitized = filter_telemetry_payload(payload)
    assert "sk_live_" not in sanitized["query_sql"]
    assert "[REDACTED_API_KEY]" in sanitized["query_sql"]
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized["aws_meta"]
    assert "[REDACTED_AWS_KEY]" in sanitized["aws_meta"]


def test_tracer_never_raises_on_telemetry_or_db_failure(
    clean_tracer: ObservabilityTracer,
) -> None:
    """Claude.md §7.3, §16: Telemetry must NEVER raise or crash the core research workflow."""
    broken_session = MagicMock()
    broken_session.add.side_effect = RuntimeError("Database disk full")
    broken_session.commit.side_effect = RuntimeError("Database disk full")

    # Recording must not raise
    evt = clean_tracer.record_event(
        session_id="sess-fail-safe",
        node_name="synthesize_answer",
        event_type="node_complete",
        payload={"answer_length": 512},
        db=broken_session,
    )
    assert evt is not None
    assert evt.node_name == "synthesize_answer"

    # Context manager must not raise telemetry exception on exit
    with clean_tracer.node(
        "sess-fail-safe", "verify_citations", db=broken_session
    ) as ctx:
        ctx.set_payload({"verified_count": 4})


def test_database_persistence_when_session_provided(
    clean_tracer: ObservabilityTracer, db_session
) -> None:
    """F16: Verify events are persisted to workflow_events table when DB session provided."""
    session_id = "sess-db-persist-1"

    # Create parent research session in DB
    research_session = ResearchSession(
        id=session_id,
        question="Which teams own Payments API?",
        status="running",
    )
    db_session.add(research_session)
    db_session.commit()

    # Record event with DB session
    evt = clean_tracer.record_event(
        session_id=session_id,
        node_name="route_retrieval",
        event_type="node_complete",
        payload={"strategy": "graph", "rule_applied": "RULE_GRAPH_OWNERSHIP"},
        latency_ms=45,
        db=db_session,
    )

    assert evt is not None

    # Query database to confirm row exists
    db_event = db_session.execute(
        select(WorkflowEvent).where(WorkflowEvent.session_id == session_id)
    ).scalar_one_or_none()

    assert db_event is not None
    assert db_event.node_name == "route_retrieval"
    assert db_event.event_type == "node_complete"
    assert db_event.latency_ms == 45
    assert db_event.payload["strategy"] == "graph"


def test_specialized_event_recorders(clean_tracer: ObservabilityTracer) -> None:
    """Verify helpers for recording queries, decisions, and tool calls."""
    session_id = "sess-specialized"

    # 1. Query execution
    q_evt = clean_tracer.record_query(
        session_id=session_id,
        store_type="sql",
        query_text="SELECT count(*) FROM incidents WHERE service_id = 'svc_1'",
        result_count=3,
        latency_ms=18,
    )
    assert q_evt.event_type == "retrieval_query"
    assert q_evt.payload["store_type"] == "sql"
    assert q_evt.payload["result_count"] == 3

    # 2. Decision recording
    d_evt = clean_tracer.record_decision(
        session_id=session_id,
        decision_type="complexity_classification",
        choice="complex",
        rationale="Canonical 4-domain query",
        rule_applied="RULE_CROSS_DOMAIN_JOIN",
    )
    assert d_evt.event_type == "decision"
    assert d_evt.payload["choice"] == "complex"
    assert d_evt.payload["rule_applied"] == "RULE_CROSS_DOMAIN_JOIN"

    # 3. Tool call recording
    t_evt = clean_tracer.record_tool_call(
        session_id=session_id,
        tool_name="cypher_traversal",
        input_args={"service": "Payments API", "depth": 2},
        output_summary="Found 4 impacted customers",
        latency_ms=32,
    )
    assert t_evt.event_type == "tool_call"
    assert t_evt.payload["tool_name"] == "cypher_traversal"
    assert t_evt.payload["latency_ms"] == 32


def test_clear_session_and_memory_isolation(clean_tracer: ObservabilityTracer) -> None:
    """Verify sessions are isolated and clear_session removes only target session events."""
    clean_tracer.record_event("sess-A", "node_1", payload={"data": "A"})
    clean_tracer.record_event("sess-B", "node_1", payload={"data": "B"})

    assert len(clean_tracer.get_events("sess-A")) == 1
    assert len(clean_tracer.get_events("sess-B")) == 1

    clean_tracer.clear_session("sess-A")

    assert len(clean_tracer.get_events("sess-A")) == 0
    assert len(clean_tracer.get_events("sess-B")) == 1


def test_global_singleton_getter() -> None:
    """Verify get_tracer returns consistent singleton tracer."""
    t1 = get_tracer()
    t2 = get_tracer()
    assert t1 is t2
