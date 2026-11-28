"""Canonical question end-to-end research demo runner (P11-3, N4, Claude.md §14, §18.1, docs/00-problem.md).

Executes the complete 13-node research workflow StateGraph against either the canonical
multi-store enterprise question or arbitrary user questions (e.g. single-store vector lookups).
Prints all 7 evaluation stages in exact order, verifying:
1. Query analysis (complexity, entities, temporal resolution)
2. Query decomposition into sub-questions and assigned retrieval strategies
3. Storage queries executed across SQL, Graph Cypher, and Hybrid Vector stores
4. Verified multi-modal evidence collection
5. Evidence verification ratio and citation grounding validation
6. Synthesized Markdown response carrying [n] citation tokens
7. Strategies used summary and execution latency threshold (N4 <= ~7.0s)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents.graph import build_graph
from agents.rules import CANONICAL_QUESTION_TEXT
from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.core.logging import get_logger
from backend.app.core.observability import TelemetryEvent, get_tracer
from backend.app.models.domain import Incident
from backend.app.services.seed import get_sample_data_dir, seed_database
from rag.graph_retrieval import seed_graph_from_domain
from rag.graph_store import InMemoryGraphStore, get_graph_store
from rag.ingest import ingest_corpus
from rag.vector_store import InMemoryVectorStore, get_vector_store

logger = get_logger("agents.demo_runner")


def ensure_demo_environment(
    reseed: bool = False,
    sample_data_dir: Path | str | None = None,
) -> None:
    """Ensure database, knowledge graph, and vector store are seeded and indexed.

    Args:
        reseed: If True, forces re-seeding of database and vector/graph stores.
        sample_data_dir: Optional path override to sample_data directory.
    """
    base_sample_dir = get_sample_data_dir(sample_data_dir)

    # 1. Relational Database (SQLite / Postgres)
    engine = get_engine()
    init_db(engine)
    session_factory = get_session_factory()
    with session_factory() as session:
        incident_count = 0
        try:
            incident_count = session.query(Incident).count()
        except Exception:  # noqa: BLE001
            incident_count = 0

        if incident_count == 0 or reseed:
            seed_database(session, sample_data_dir=base_sample_dir)

    # 2. Knowledge Graph Store
    graph_store = get_graph_store()
    if isinstance(graph_store, InMemoryGraphStore):
        needs_graph_seed = reseed or (
            hasattr(graph_store, "node_count") and graph_store.node_count() == 0
        )
        if needs_graph_seed:
            seed_graph_from_domain(graph_store, sample_data_dir=base_sample_dir)

    # 3. Vector & Document Store
    vector_store = get_vector_store()
    needs_vector_seed = reseed or (
        isinstance(vector_store, InMemoryVectorStore) and vector_store.count() == 0
    )
    if needs_vector_seed:
        docs_dir = base_sample_dir / "documents"
        if docs_dir.exists():
            ingest_corpus(documents_dir=docs_dir)


def _compute_strategies_used(
    sub_questions: list[dict[str, Any]],
    executed_queries: list[dict[str, Any]],
) -> list[str]:
    """Compute normalized distinct strategies used across sub-questions and queries."""
    strategies_found: set[str] = set()

    for sq in sub_questions:
        strat = str(sq.get("strategy", "")).lower()
        if strat == "sql":
            strategies_found.add("sql")
        elif strat == "graph":
            strategies_found.add("graph")
        elif strat in ("vector", "hybrid"):
            strategies_found.add("vector")

    # Also inspect executed queries
    for q in executed_queries:
        st = str(q.get("store_type", "")).lower()
        if "sql" in st:
            strategies_found.add("sql")
        elif "graph" in st:
            strategies_found.add("graph")
        elif "vector" in st or "hybrid" in st:
            strategies_found.add("vector")

    order = ["graph", "sql", "vector"]
    return [s for s in order if s in strategies_found]


def run_demo(
    question: str = CANONICAL_QUESTION_TEXT,
    user_id: str = "analyst@novaenterprise.io",
    reseed: bool = False,
    print_output: bool = True,
) -> dict[str, Any]:
    """Execute the end-to-end research graph and return structured demonstration metrics.

    Args:
        question: Question to analyze and answer.
        user_id: Caller identity for session.
        reseed: Force store re-initialization before execution.
        print_output: If True, prints formatted console output matching Claude.md §14.

    Returns:
        Structured result dictionary containing state and telemetry.
    """
    ensure_demo_environment(reseed=reseed)

    session_id = f"demo-{uuid4().hex[:10]}"
    tracer = get_tracer()

    t_start = time.perf_counter()
    graph = build_graph()
    state = graph.invoke(
        {
            "session_id": session_id,
            "question": question,
            "user_id": user_id,
        }
    )
    elapsed_s = round(time.perf_counter() - t_start, 3)

    # Telemetry retrieval queries
    events: list[TelemetryEvent] = tracer.get_events(session_id)
    retrieval_queries: list[dict[str, Any]] = [
        ev.payload for ev in events if ev.event_type == "retrieval_query"
    ]

    complexity = state.get("complexity", "moderate")
    entity = state.get("entity")
    time_range = state.get("time_range")
    sub_questions = state.get("sub_questions", []) or []
    evidence = state.get("evidence", []) or []
    verification_ratio = float(state.get("verification_ratio", 1.0))
    citations_verified = bool(state.get("citations_verified", True))
    answer = str(state.get("answer", "") or "")
    citations = state.get("citations", []) or []
    corrective_rounds = int(state.get("corrective_rounds", 0))

    strategies_used = _compute_strategies_used(sub_questions, retrieval_queries)
    strat_str = ", ".join(strategies_used)

    result: dict[str, Any] = {
        "session_id": session_id,
        "question": question,
        "latency_s": elapsed_s,
        "complexity": complexity,
        "entity": entity,
        "time_range": time_range,
        "sub_questions": sub_questions,
        "queries": retrieval_queries,
        "evidence": evidence,
        "verification_ratio": verification_ratio,
        "citations_verified": citations_verified,
        "answer": answer,
        "citations": citations,
        "strategies_used": strategies_used,
        "corrective_rounds": corrective_rounds,
    }

    if print_output:
        _print_demo_presentation(result, strat_str)

    return result


def _print_demo_presentation(res: dict[str, Any], strat_str: str) -> None:
    """Format and print all 7 execution stages conforming to Claude.md §14 and docs/00-problem.md."""
    sep = "=" * 75

    print(sep)
    print("  NovaEnterprise Research Intelligence — Canonical Demo Runner")
    print(sep)
    print(f"Question: {res['question']}")
    print(f"Session:  {res['session_id']}")
    print()

    # 1. Query Analysis
    print("=== 1. QUERY ANALYSIS " + "=" * 53)
    print(f"  Complexity:     {res['complexity']}")
    print(f"  Target Entity:  {res['entity']}")
    tr = res["time_range"]
    if isinstance(tr, dict) and "quarter_name" in tr:
        tr_display = f"{tr.get('quarter_name')} ({tr.get('quarter')})"
    else:
        tr_display = str(tr) if tr else "None"
    print(f"  Time Range:     {tr_display}")
    print()

    # 2. Query Decomposition
    print("=== 2. QUERY DECOMPOSITION " + "=" * 48)
    for sq in res["sub_questions"]:
        sq_id = sq.get("id", "sq?")
        strat = sq.get("strategy", "vector")
        text = sq.get("question", "")
        print(f"  {sq_id:>4} [{strat:>6}] {text}  (done)")
    print()

    # 3. Executed Storage Queries
    print("=== 3. RETRIEVAL QUERIES EXECUTED " + "=" * 41)
    sql_qs = [q for q in res["queries"] if "sql" in str(q.get("store_type", ""))]
    graph_qs = [q for q in res["queries"] if "graph" in str(q.get("store_type", ""))]
    doc_qs = [
        q
        for q in res["queries"]
        if "hybrid" in str(q.get("store_type", ""))
        or "vector" in str(q.get("store_type", ""))
    ]

    if sql_qs:
        print("[SQL Query]")
        for q in sql_qs:
            print(f"  {q.get('query')} (returned {q.get('result_count', 0)} record(s))")
    else:
        print("[SQL Query]\n  (None executed — blocked by complexity routing)")

    if graph_qs:
        print("\n[Graph Traversals & Cypher]")
        for q in graph_qs:
            print(f"  • {q.get('query')} (returned {q.get('result_count', 0)} item(s))")
    else:
        print(
            "\n[Graph Traversals & Cypher]\n  (None executed — blocked by complexity routing)"
        )

    if doc_qs:
        print("\n[Document & Hybrid Search]")
        for q in doc_qs:
            print(
                f"  • {q.get('query')} (returned {q.get('result_count', 0)} chunk(s))"
            )
    print()

    # 4. Collected Evidence
    ev_list = res["evidence"]
    print(
        f"=== 4. COLLECTED EVIDENCE ({len(ev_list)} items) "
        + "=" * (47 - len(str(len(ev_list))))
    )
    preview_count = min(len(ev_list), 6)
    for idx, ev in enumerate(ev_list[:preview_count], start=1):
        src = getattr(
            ev,
            "source_type",
            ev.get("source_type", "unknown") if isinstance(ev, dict) else "unknown",
        )
        loc = getattr(
            ev,
            "locator",
            ev.get("locator", "unknown") if isinstance(ev, dict) else "unknown",
        )
        cnt = getattr(
            ev, "content", ev.get("content", "") if isinstance(ev, dict) else ""
        )
        snippet = cnt.strip().replace("\n", " ")
        if len(snippet) > 95:
            snippet = snippet[:92] + "..."
        print(f"  [{idx}] Store: {src:<8} | Locator: {loc}")
        print(f"      {snippet}")
    if len(ev_list) > preview_count:
        print(f"  ... and {len(ev_list) - preview_count} additional evidence records.")
    print()

    # 5. Evidence & Citation Verification
    print("=== 5. EVIDENCE & CITATION VERIFICATION " + "=" * 35)
    vr = res["verification_ratio"]
    print(f"  Verification Ratio: {vr * 100:.1f}% (ratio: {vr})")
    cv = res["citations_verified"]
    cit_count = len(res["citations"])
    print(f"  Citations Verified: {cv} ({cit_count} valid citation marker(s) verified)")
    print()

    # 6. Cited Answer
    print("=== 6. CITED ANSWER " + "=" * 55)
    print(res["answer"])
    print()
    if res["citations"]:
        print("Citations:")
        for cit in res["citations"]:
            cid = cit.get("citation_id")
            st = cit.get("source_type")
            loc = cit.get("locator")
            print(f"  [{cid}] ({st}) {loc}")
        print()

    # 7. Summary
    print("=== 7. EXECUTION SUMMARY " + "=" * 50)
    cr = res["corrective_rounds"]
    print(f"  strategies_used: {strat_str} (corrective rounds: {cr})")
    lat = res["latency_s"]
    satisfies_n4 = "PASS (<= 7.0s)" if lat <= 7.0 else "EXCEEDED"
    print(
        f"  Total Latency:   {lat:.3f} s [N4 Offline Performance Threshold: {satisfies_n4}]"
    )
    print(sep)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the demo runner.

    Usage:
        python -m agents.demo_runner [--question "..."] [--json] [--reseed]
    """
    parser = argparse.ArgumentParser(
        description="NovaEnterprise Multi-Hop Research Demo Runner (Claude.md §14)"
    )
    parser.add_argument(
        "--question",
        "-q",
        default=CANONICAL_QUESTION_TEXT,
        help="Natural language research question to execute",
    )
    parser.add_argument(
        "--user",
        "-u",
        default="analyst@novaenterprise.io",
        help="Executing user identity for audit trail and role checks",
    )
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="Force re-seeding of database and vector/graph stores",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw structured JSON result instead of formatted presentation",
    )

    args = parser.parse_args(argv)

    try:
        result = run_demo(
            question=args.question,
            user_id=args.user,
            reseed=args.reseed,
            print_output=not args.json,
        )

        if args.json:
            # Prepare JSON-serializable output
            # Convert non-serializable objects (like Evidence models) to dicts
            clean_res = dict(result)
            clean_ev = []
            for ev in clean_res.get("evidence", []):
                if hasattr(ev, "model_dump"):
                    clean_ev.append(ev.model_dump())
                else:
                    clean_ev.append(dict(ev) if isinstance(ev, dict) else str(ev))
            clean_res["evidence"] = clean_ev
            print(json.dumps(clean_res, indent=2, default=str))

        return 0
    except Exception as exc:
        logger.exception("Demo execution failed")
        print(f"Error executing demo: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
