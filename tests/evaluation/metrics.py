"""Evaluation metric computation modules for CI threshold verification (P14-1, Claude.md §3.3, docs/01-prd.md §5).

Computes the 6 core metrics:
1. retrieval_relevance (threshold >= 0.80)
2. sql_correctness     (threshold == 1.00)
3. graph_correctness   (threshold == 1.00)
4. multi_hop_coverage  (threshold >= 0.66)
5. citation_support    (threshold == 1.00)
6. answer_grounding    (threshold >= 0.50)
"""

from __future__ import annotations

import re
from typing import Any

from rag.sql_retrieval import validate_sql

FORBIDDEN_CYPHER_KEYWORDS = {"CREATE", "MERGE", "DELETE", "SET", "DROP", "DETACH"}


def calculate_retrieval_relevance(
    cases: list[dict[str, Any]], results: list[dict[str, Any]]
) -> float:
    """Calculate retrieval relevance metric across evaluation test cases.

    Evaluates:
    - Expected retrieval strategies selected by agent query decomposition.
    - Proportion of retrieved evidence items originating from relevant stores.

    Threshold: >= 0.80 (Observed: 1.00).
    """
    if not cases:
        return 0.0

    case_scores: list[float] = []

    for case, res in zip(cases, results, strict=False):
        expected_strats = set(case.get("expected_strategies", []))
        strategies_used = set(res.get("strategies_used", []))
        sub_questions = res.get("sub_questions", [])
        for sq in sub_questions:
            strat = sq.get("strategy")
            if strat:
                if strat in ("vector", "hybrid"):
                    strategies_used.add("vector")
                else:
                    strategies_used.add(strat)

        # Normalize vector/hybrid
        norm_expected = {"vector" if s == "hybrid" else s for s in expected_strats}
        norm_used = {"vector" if s == "hybrid" else s for s in strategies_used}

        # Strategy recall
        overlap = len(norm_expected.intersection(norm_used))
        strat_score = overlap / len(norm_expected) if norm_expected else 1.0

        # Evidence validity
        evidence = res.get("evidence", [])
        if evidence:
            valid_evidence_count = 0
            for ev in evidence:
                src_type = (
                    ev.source_type
                    if hasattr(ev, "source_type")
                    else ev.get("source_type")
                )
                if src_type in norm_expected or (
                    src_type == "document" and "vector" in norm_expected
                ):
                    valid_evidence_count += 1
            evidence_score = valid_evidence_count / len(evidence)
        else:
            evidence_score = 1.0 if not norm_expected else 0.0

        case_scores.append(round(0.5 * strat_score + 0.5 * evidence_score, 4))

    return round(sum(case_scores) / len(case_scores), 4)


def calculate_sql_correctness(
    cases: list[dict[str, Any]], results: list[dict[str, Any]]
) -> float:
    """Calculate SQL correctness metric across evaluation test cases.

    Evaluates:
    - Read-only allowlist compliance via validate_sql().
    - Expected table targeting and non-empty result generation when SQL is required.
    - Zero SQL queries executed when question does not require SQL.

    Threshold: == 1.00 (Observed: 1.00).
    """
    if not cases:
        return 0.0

    case_scores: list[float] = []

    for case, res in zip(cases, results, strict=False):
        expected_strats = case.get("expected_strategies", [])
        needs_sql = "sql" in expected_strats
        expected_tables = case.get("expected_sql_tables", [])

        queries = res.get("queries", [])
        sql_queries = [q for q in queries if q.get("store_type") == "sql"]

        if needs_sql:
            if not sql_queries:
                case_scores.append(0.0)
                continue

            query_valid = True
            for sq in sql_queries:
                q_text = sq.get("query", "")
                # Must pass read-only allowlist validation
                if not validate_sql(q_text):
                    query_valid = False
                    break
                # Must target expected table(s) if specified
                if expected_tables and not any(
                    tbl in q_text.lower() for tbl in expected_tables
                ):
                    query_valid = False
                    break
                # Must produce valid non-empty result rows
                if sq.get("result_count", 0) <= 0:
                    query_valid = False
                    break

            case_scores.append(1.0 if query_valid else 0.0)
        else:
            # When SQL is not needed, exactly zero SQL queries should be run
            case_scores.append(1.0 if len(sql_queries) == 0 else 0.0)

    return round(sum(case_scores) / len(case_scores), 4)


def calculate_graph_correctness(
    cases: list[dict[str, Any]], results: list[dict[str, Any]]
) -> float:
    """Calculate knowledge graph correctness metric across evaluation test cases.

    Evaluates:
    - Read-only Cypher query validation (zero mutation clauses).
    - Expected relationship types targeted when graph retrieval is required.
    - Zero Cypher queries executed when question does not require graph.

    Threshold: == 1.00 (Observed: 1.00).
    """
    if not cases:
        return 0.0

    case_scores: list[float] = []

    for case, res in zip(cases, results, strict=False):
        expected_strats = case.get("expected_strategies", [])
        needs_graph = "graph" in expected_strats
        expected_rels = case.get("expected_cypher_relationships", [])

        queries = res.get("queries", [])
        graph_queries = [q for q in queries if q.get("store_type") == "graph"]
        evidence = res.get("evidence", [])
        graph_evidence = [
            e
            for e in evidence
            if (e.source_type if hasattr(e, "source_type") else e.get("source_type"))
            == "graph"
        ]

        if needs_graph:
            if not graph_queries:
                case_scores.append(0.0)
                continue

            query_valid = True
            for gq in graph_queries:
                cypher = str(gq.get("query", ""))
                tokens = set(re.findall(r"\b[A-Z]+\b", cypher))
                if tokens.intersection(FORBIDDEN_CYPHER_KEYWORDS):
                    query_valid = False
                    break
                # Must return results
                if gq.get("result_count", 0) <= 0:
                    query_valid = False
                    break

            if not query_valid:
                case_scores.append(0.0)
                continue

            # Must reference expected relationships if specified across queries/evidence locators
            if expected_rels:
                all_locators_and_queries = " ".join(
                    [q.get("query", "") for q in graph_queries]
                    + [
                        (
                            e.locator
                            if hasattr(e, "locator")
                            else str(e.get("locator", ""))
                        )
                        for e in graph_evidence
                    ]
                )
                if not any(rel in all_locators_and_queries for rel in expected_rels):
                    case_scores.append(0.0)
                    continue

            case_scores.append(1.0)
        else:
            # When Graph is not needed, exactly zero graph queries should be run
            case_scores.append(1.0 if len(graph_queries) == 0 else 0.0)

    return round(sum(case_scores) / len(case_scores), 4)


def calculate_multi_hop_coverage(
    cases: list[dict[str, Any]], results: list[dict[str, Any]]
) -> float:
    """Calculate multi-hop decomposition and coverage metric across evaluation test cases.

    Evaluates:
    - Proportion of required domain hops covered by sub-questions and evidence.

    Threshold: >= 0.66 (Observed: 1.00).
    """
    if not cases:
        return 0.0

    case_scores: list[float] = []

    for case, res in zip(cases, results, strict=False):
        requires_multi_hop = case.get("requires_multi_hop", False)
        expected_hops = case.get("expected_hops", [])

        if not requires_multi_hop or not expected_hops:
            # Single-hop question automatically achieves 1.00 if retrieved
            case_scores.append(1.0)
            continue

        sub_questions = res.get("sub_questions", [])
        evidence = res.get("evidence", [])
        combined_text = " ".join(
            [sq.get("question") or sq.get("text") or "" for sq in sub_questions]
            + [
                (ev.content if hasattr(ev, "content") else str(ev.get("content", "")))
                for ev in evidence
            ]
        ).lower()

        # Check coverage of each expected hop keyword/domain
        hops_covered = 0
        for hop in expected_hops:
            hop_terms = hop.lower().split("_")
            if any(term in combined_text for term in hop_terms):
                hops_covered += 1

        coverage = hops_covered / len(expected_hops) if expected_hops else 1.0
        case_scores.append(round(coverage, 4))

    return round(sum(case_scores) / len(case_scores), 4)


def calculate_citation_support(
    cases: list[dict[str, Any]], results: list[dict[str, Any]]
) -> float:
    """Calculate citation support metric across evaluation test cases.

    Evaluates:
    - Presence of sequential [n] citation tokens in synthesized answers.
    - 100% resolution of answer citation tokens to valid evidence locators.
    - Zero dangling or unresolvable citations.

    Threshold: == 1.00 (Observed: 1.00).
    """
    if not cases:
        return 0.0

    case_scores: list[float] = []

    for case, res in zip(cases, results, strict=False):
        answer = res.get("answer", "")
        citations = res.get("citations", [])
        unresolved = res.get("unresolved_citations", [])
        citations_verified = res.get("citations_verified", False)

        tokens = [int(m) for m in re.findall(r"\[(\d+)\]", answer)]
        min_citations = case.get("min_citations", 1)

        if len(tokens) < min_citations or not citations:
            case_scores.append(0.0)
            continue

        if unresolved or not citations_verified:
            case_scores.append(0.0)
            continue

        # Check that all citation objects have valid source_type and locator
        all_valid = True
        for cit in citations:
            src = (
                cit.get("source_type")
                if isinstance(cit, dict)
                else getattr(cit, "source_type", None)
            )
            loc = (
                cit.get("locator")
                if isinstance(cit, dict)
                else getattr(cit, "locator", None)
            )
            if not src or not loc:
                all_valid = False
                break

        case_scores.append(1.0 if all_valid else 0.0)

    return round(sum(case_scores) / len(case_scores), 4)


def calculate_answer_grounding(
    cases: list[dict[str, Any]], results: list[dict[str, Any]]
) -> float:
    """Calculate answer grounding and factual faithfulness metric across evaluation test cases.

    Evaluates:
    - Claim verification ratio >= 0.80.
    - Presence of verified domain facts and entities without hallucination.

    Threshold: >= 0.50 (Observed: 1.00).
    """
    if not cases:
        return 0.0

    case_scores: list[float] = []

    for case, res in zip(cases, results, strict=False):
        answer = res.get("answer", "")
        evidence = res.get("evidence", [])
        verification_ratio = float(res.get("verification_ratio", 0.0))
        expected_facts = case.get("expected_key_facts", [])

        # Check verification ratio threshold
        ratio_score = 1.0 if verification_ratio >= 0.8 else (verification_ratio / 0.8)

        # Check expected fact coverage
        evidence_text = " ".join(
            [
                (ev.content if hasattr(ev, "content") else str(ev.get("content", "")))
                for ev in evidence
            ]
        )
        full_corpus = (answer + " " + evidence_text).lower()

        facts_found = 0
        for fact in expected_facts:
            if fact.lower() in full_corpus:
                facts_found += 1

        fact_score = facts_found / len(expected_facts) if expected_facts else 1.0

        score = 0.5 * ratio_score + 0.5 * fact_score
        case_scores.append(round(score, 4))

    return round(sum(case_scores) / len(case_scores), 4)
