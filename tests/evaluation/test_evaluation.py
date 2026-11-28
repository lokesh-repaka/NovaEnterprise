"""Evaluation test suite asserting the 6 CI metric thresholds (P14-1, Claude.md §3.3).

Verifies offline that:
- retrieval relevance >= 0.80
- SQL correctness == 1.00
- graph correctness == 1.00
- multi-hop coverage >= 0.66
- citation support == 1.00
- answer grounding >= 0.50
"""

from __future__ import annotations

import pytest

from tests.evaluation.evaluate import CI_THRESHOLDS, run_evaluation


@pytest.fixture(scope="module")
def eval_results() -> tuple[dict[str, float], bool]:
    """Execute evaluation harness once for the module and yield scores."""
    scores, all_passed = run_evaluation(print_table=False)
    return scores, all_passed


def test_eval_retrieval_relevance(eval_results: tuple[dict[str, float], bool]) -> None:
    """CI Threshold: retrieval relevance >= 0.80."""
    scores, _ = eval_results
    assert scores["retrieval_relevance"] >= CI_THRESHOLDS["retrieval_relevance"]
    assert scores["retrieval_relevance"] == 1.00


def test_eval_sql_correctness(eval_results: tuple[dict[str, float], bool]) -> None:
    """CI Threshold: SQL correctness == 1.00."""
    scores, _ = eval_results
    assert scores["sql_correctness"] == CI_THRESHOLDS["sql_correctness"]
    assert scores["sql_correctness"] == 1.00


def test_eval_graph_correctness(eval_results: tuple[dict[str, float], bool]) -> None:
    """CI Threshold: graph correctness == 1.00."""
    scores, _ = eval_results
    assert scores["graph_correctness"] == CI_THRESHOLDS["graph_correctness"]
    assert scores["graph_correctness"] == 1.00


def test_eval_multi_hop_coverage(eval_results: tuple[dict[str, float], bool]) -> None:
    """CI Threshold: multi-hop coverage >= 0.66."""
    scores, _ = eval_results
    assert scores["multi_hop"] >= CI_THRESHOLDS["multi_hop"]
    assert scores["multi_hop"] == 1.00


def test_eval_citation_support(eval_results: tuple[dict[str, float], bool]) -> None:
    """CI Threshold: citation support == 1.00."""
    scores, _ = eval_results
    assert scores["citation_support"] == CI_THRESHOLDS["citation_support"]
    assert scores["citation_support"] == 1.00


def test_eval_answer_grounding(eval_results: tuple[dict[str, float], bool]) -> None:
    """CI Threshold: answer grounding >= 0.50."""
    scores, _ = eval_results
    assert scores["answer_grounding"] >= CI_THRESHOLDS["answer_grounding"]
    assert scores["answer_grounding"] == 1.00


def test_eval_overall_ci_gate(eval_results: tuple[dict[str, float], bool]) -> None:
    """Overall CI Gate: all 6 thresholds pass simultaneously."""
    _, all_passed = eval_results
    assert all_passed is True
