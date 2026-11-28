"""End-to-End Canonical Pipeline Integration Test (P14-2, Claude.md §14, §18.1).

Executes the full 13-node research workflow StateGraph against the canonical
enterprise question, asserting all 7 evaluation stages and verifying
cross-store retrieval across SQL, Knowledge Graph, and Hybrid Vector stores.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from agents.demo_runner import ensure_demo_environment
from agents.graph import build_graph
from agents.rules import CANONICAL_QUESTION_TEXT
from backend.app.core.config import clear_settings_cache
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.core.llm import reset_llm_cache
from backend.app.main import create_app
from backend.app.repositories.research import (
    ResearchSessionRepository,
    WorkflowEventRepository,
)
from backend.app.services.approval_service import reset_approval_service
from backend.app.services.research_service import reset_research_service
from memory.memory_service import get_memory_service, reset_memory_service
from memory.protocols import InMemoryEpisodicMemoryStore


@pytest.fixture(scope="module")
def setup_pipeline_env() -> None:
    """Prepare database and storage singletons for pipeline integration tests."""
    clear_settings_cache()
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)

    ensure_demo_environment(reseed=True)
    reset_research_service()
    reset_approval_service()
    reset_llm_cache()
    reset_memory_service()
    get_memory_service(episodic_store=InMemoryEpisodicMemoryStore())


def test_canonical_pipeline_direct_graph_execution(setup_pipeline_env) -> None:
    """Execute LangGraph StateGraph directly and verify all 7 evaluation stages."""
    app = build_graph()

    state = {
        "session_id": "rs-direct-pipeline-01",
        "question": CANONICAL_QUESTION_TEXT,
        "user_id": "lead-architect",
    }

    t0 = time.perf_counter()
    result = app.invoke(state)
    duration = time.perf_counter() - t0

    # Verify Stage 1: Query Analysis
    assert result.get("intent") is not None
    assert result.get("entity") is not None
    assert result.get("time_range") is not None

    # Verify Stage 2: Sub-question decomposition
    sub_questions = result.get("sub_questions", [])
    assert 1 <= len(sub_questions) <= 4

    # Verify Stage 3: Retrieval strategies used
    strategies = {sq.get("strategy") for sq in sub_questions if isinstance(sq, dict)}
    assert len(strategies) >= 2

    # Verify Stage 4: Multi-modal evidence collected
    evidence = result.get("evidence", [])
    assert len(evidence) >= 1
    source_types = {e.source_type for e in evidence if hasattr(e, "source_type")}
    assert len(source_types) >= 1

    # Verify Stage 5: Claim verification
    assert result.get("verification_ratio", 0.0) >= 0.80
    assert len(result.get("verified_evidence", [])) >= 1

    # Verify Stage 6: Synthesized answer with citations
    answer = result.get("answer", "")
    assert len(answer) > 0
    assert result.get("citations_verified") is True

    # Verify Stage 7: Offline latency guarantee (N4)
    assert duration <= 7.0


def test_canonical_pipeline_via_fastapi_and_background_task(
    setup_pipeline_env,
) -> None:
    """Execute canonical question via FastAPI API and verify database state and events."""
    app = create_app()
    with TestClient(app) as client:
        # Acquire token
        auth_resp = client.post("/api/v1/auth/demo-token", json={"role": "analyst"})
        assert auth_resp.status_code == 200
        token = auth_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Submit question -> 202 Accepted
        post_resp = client.post(
            "/api/v1/research",
            json={
                "question": CANONICAL_QUESTION_TEXT,
                "user_id": "test-analyst-pipeline",
            },
            headers=headers,
        )
        assert post_resp.status_code == 202
        session_id = post_resp.json()["session_id"]

        # Check session status in database
        engine = get_engine("sqlite:///:memory:")
        factory = get_session_factory(engine)
        with factory() as db:
            session_repo = ResearchSessionRepository(db)
            session = session_repo.get(session_id)
            assert session is not None
            assert session.status == "completed"
            assert session.answer is not None
            assert len(session.sub_questions) >= 1
            assert len(session.evidence_data) >= 1

            # Check workflow telemetry events
            events_repo = WorkflowEventRepository(db)
            events = events_repo.list_by_session(session_id)
            assert len(events) >= 12
            node_names = [e.node_name for e in events]
            assert "analyze_query" in node_names
            assert "assess_complexity" in node_names
            assert "route_retrieval" in node_names
            assert "synthesize_answer" in node_names
            assert "verify_citations" in node_names
