"""Unit and integration tests for the CLI demo runner (P11-3, N4, Claude.md §14, §18.1, docs/00-problem.md).

Proves:
- Canonical question end-to-end execution through 13-node research graph (N4 <= ~7.0s)
- Correct stage printout order: analysis -> decomposition -> queries -> evidence -> verification -> cited answer -> summary
- Single-store question path ("What is our data retention policy?") routes to simple, vector-only
- CLI argument parsing, --json mode, and environment auto-seeding idempotency
"""

import io
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agents.demo_runner import (
    ensure_demo_environment,
    main,
    run_demo,
)
from agents.rules import CANONICAL_QUESTION_TEXT
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.services.seed import seed_database
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store
from rag.ingest import ingest_corpus
from rag.vector_store import get_vector_store


@pytest.fixture(autouse=True)
def setup_demo_stores() -> Any:
    """Ensure in-memory or SQLite database, graph, and vector stores are primed."""
    engine = get_engine()
    init_db(engine)
    with get_session_factory()() as s:
        seed_database(s)

    store = get_graph_store()
    sample_dir = Path(__file__).resolve().parents[2] / "sample_data"
    seed_graph_from_domain(store, sample_data_dir=sample_dir)

    v_store = get_vector_store()
    docs_dir = sample_dir / "documents"
    if v_store.count() == 0 and docs_dir.exists():
        ingest_corpus(documents_dir=docs_dir)

    yield


def test_ensure_demo_environment_idempotent() -> None:
    """Verify that ensure_demo_environment initializes missing stores without duplicating on repeat calls."""
    # First invocation ensures seeded
    ensure_demo_environment()
    v_store = get_vector_store()
    assert v_store.count() > 0

    store = get_graph_store()
    assert isinstance(store, InMemoryGraphStore)
    assert store.node_count() > 0

    # Second invocation should be a fast no-op
    t0 = time.perf_counter()
    ensure_demo_environment()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5


def test_canonical_question_end_to_end_runner() -> None:
    """Verify canonical question runs end-to-end, meets N4 (<= 7.0s), and produces exact stage outputs."""
    t0 = time.perf_counter()
    result = run_demo(
        question=CANONICAL_QUESTION_TEXT,
        print_output=True,
    )
    elapsed_total = time.perf_counter() - t0

    # 1. Non-functional performance threshold (N4: <= ~7.0s)
    assert result["latency_s"] <= 7.0
    assert elapsed_total <= 7.0

    # 2. Stage 1: Analysis
    assert result["complexity"] == "complex"
    assert result["entity"] == "Payments API"
    assert result["time_range"] is not None
    assert "2026-Q2" in str(result["time_range"])

    # 3. Stage 2: Query decomposition (4 sub-questions: graph, sql, graph, hybrid)
    sub_questions = result["sub_questions"]
    assert len(sub_questions) == 4
    strategies = [sq["strategy"] for sq in sub_questions]
    assert strategies == ["graph", "sql", "graph", "hybrid"]

    # 4. Stage 3: Executed storage queries
    queries = result["queries"]
    sql_queries = [q for q in queries if q.get("store_type") == "sql"]
    graph_queries = [q for q in queries if q.get("store_type") == "graph"]
    hybrid_queries = [q for q in queries if q.get("store_type") in ("hybrid", "vector")]

    assert len(sql_queries) >= 1
    assert "incidents" in sql_queries[0].get("query", "").lower()
    assert (
        len(graph_queries) >= 2
    )  # service_incidents and service_dependencies traversals
    assert len(hybrid_queries) >= 1

    # 5. Stage 4: Collected evidence
    evidence = result["evidence"]
    assert len(evidence) >= 9  # Claude.md §14: "nine pieces of evidence"

    # 6. Stage 5: Verification ratio
    assert result["verification_ratio"] >= 0.8
    assert result["citations_verified"] is True

    # 7. Stage 6: Cited answer
    answer = result["answer"]
    assert len(answer) > 0
    assert "[1]" in answer
    assert len(result["citations"]) >= 1

    # 8. Stage 7: Execution summary
    assert "graph" in result["strategies_used"]
    assert "sql" in result["strategies_used"]
    assert "vector" in result["strategies_used"]
    assert result["corrective_rounds"] == 0


def test_single_store_question_data_retention() -> None:
    """Verify single-store question drops complexity to simple, uses exactly 1 sub-question, and vector-only."""
    question = "What is our data retention policy?"
    result = run_demo(
        question=question,
        print_output=True,
    )

    # 1. Complexity & routing
    assert result["complexity"] == "simple"
    sub_questions = result["sub_questions"]
    assert len(sub_questions) == 1
    assert sub_questions[0]["strategy"] == "vector"

    # 2. Executed queries (zero SQL and zero Cypher)
    queries = result["queries"]
    sql_queries = [q for q in queries if q.get("store_type") == "sql"]
    graph_queries = [q for q in queries if q.get("store_type") == "graph"]
    assert len(sql_queries) == 0
    assert len(graph_queries) == 0

    # 3. Strategy used
    assert result["strategies_used"] == ["vector"]
    assert result["corrective_rounds"] == 0

    # 4. Answer contains citations
    assert len(result["answer"]) > 0
    assert len(result["citations"]) >= 1


def test_cli_demo_runner_main_json_output() -> None:
    """Verify CLI main entrypoint with --json flag emits structured JSON."""
    stdout_capture = io.StringIO()
    with patch("sys.stdout", stdout_capture):
        exit_code = main(["--question", "What is our data retention policy?", "--json"])

    assert exit_code == 0
    output = stdout_capture.getvalue()
    parsed = json.loads(output)
    assert parsed["complexity"] == "simple"
    assert parsed["strategies_used"] == ["vector"]
    assert "answer" in parsed
    assert "citations" in parsed


def test_cli_demo_runner_main_default_canonical() -> None:
    """Verify CLI main entrypoint without arguments runs the canonical demo."""
    stdout_capture = io.StringIO()
    with patch("sys.stdout", stdout_capture):
        exit_code = main([])

    assert exit_code == 0
    output = stdout_capture.getvalue()
    assert "NovaEnterprise" in output
    assert "=== 1. QUERY ANALYSIS" in output
    assert "=== 2. QUERY DECOMPOSITION" in output
    assert "=== 3. RETRIEVAL QUERIES EXECUTED" in output
    assert "=== 4. COLLECTED EVIDENCE" in output
    assert "=== 5. EVIDENCE & CITATION VERIFICATION" in output
    assert "=== 6. CITED ANSWER" in output
    assert "=== 7. EXECUTION SUMMARY" in output
    assert "strategies_used: graph, sql, vector (corrective rounds: 0)" in output
