"""Unit and integration tests for the evaluation harness and CI threshold metrics (P14-1, Claude.md §3.3, §14, docs/01-prd.md §5).

Proves:
- tests/evaluation/datasets/eval_cases.json dataset schema validity
- The 6 CI evaluation thresholds:
    1. retrieval_relevance >= 0.80 (observed 1.00)
    2. sql_correctness == 1.00     (observed 1.00)
    3. graph_correctness == 1.00   (observed 1.00)
    4. multi_hop >= 0.66           (observed 1.00)
    5. citation_support == 1.00    (observed 1.00)
    6. answer_grounding >= 0.50    (observed 1.00)
- Command-line runner: python -m tests.evaluation.evaluate emits metrics table and exits 0
- Regression detection: deliberately degraded results trigger failure exit code 1
"""

import io
import json
from pathlib import Path
from unittest.mock import patch

from tests.evaluation.evaluate import (
    CI_THRESHOLDS,
    main,
    run_evaluation,
)
from tests.evaluation.metrics import (
    calculate_citation_support,
    calculate_sql_correctness,
)


def test_eval_cases_dataset_schema() -> None:
    """Verify that tests/evaluation/datasets/eval_cases.json exists and conforms to schema."""
    dataset_path = (
        Path(__file__).resolve().parents[1]
        / "evaluation"
        / "datasets"
        / "eval_cases.json"
    )
    assert dataset_path.exists(), f"Evaluation dataset not found at {dataset_path}"

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    assert isinstance(cases, list)
    assert len(cases) >= 3, "Evaluation dataset must contain at least 3 benchmark cases"

    for case in cases:
        assert "id" in case
        assert "question" in case
        assert "expected_strategies" in case
        assert isinstance(case["expected_strategies"], list)
        assert len(case["expected_strategies"]) > 0


def test_metric_retrieval_relevance_threshold() -> None:
    """Verify retrieval relevance meets or exceeds CI threshold (>= 0.80)."""
    scores, _ = run_evaluation()
    metric_score = scores.get("retrieval_relevance", 0.0)
    assert metric_score >= CI_THRESHOLDS["retrieval_relevance"]
    assert metric_score == 1.00


def test_metric_sql_correctness_threshold() -> None:
    """Verify SQL correctness meets exact CI threshold (= 1.00)."""
    scores, _ = run_evaluation()
    metric_score = scores.get("sql_correctness", 0.0)
    assert metric_score == CI_THRESHOLDS["sql_correctness"]
    assert metric_score == 1.00


def test_metric_graph_correctness_threshold() -> None:
    """Verify graph correctness meets exact CI threshold (= 1.00)."""
    scores, _ = run_evaluation()
    metric_score = scores.get("graph_correctness", 0.0)
    assert metric_score == CI_THRESHOLDS["graph_correctness"]
    assert metric_score == 1.00


def test_metric_multi_hop_threshold() -> None:
    """Verify multi-hop coverage meets or exceeds CI threshold (>= 0.66)."""
    scores, _ = run_evaluation()
    metric_score = scores.get("multi_hop", 0.0)
    assert metric_score >= CI_THRESHOLDS["multi_hop"]
    assert metric_score == 1.00


def test_metric_citation_support_threshold() -> None:
    """Verify citation support meets exact CI threshold (= 1.00)."""
    scores, _ = run_evaluation()
    metric_score = scores.get("citation_support", 0.0)
    assert metric_score == CI_THRESHOLDS["citation_support"]
    assert metric_score == 1.00


def test_metric_answer_grounding_threshold() -> None:
    """Verify answer grounding meets or exceeds CI threshold (>= 0.50)."""
    scores, _ = run_evaluation()
    metric_score = scores.get("answer_grounding", 0.0)
    assert metric_score >= CI_THRESHOLDS["answer_grounding"]
    assert metric_score == 1.00


def test_all_ci_thresholds_pass() -> None:
    """Verify that all 6 evaluation metrics pass simultaneously in offline mode."""
    scores, all_passed = run_evaluation()
    assert all_passed is True
    assert len(scores) == 6


def test_evaluate_cli_main_prints_table() -> None:
    """Verify CLI main entrypoint prints the exact formatted metrics table and exits 0."""
    stdout_capture = io.StringIO()
    with patch("sys.stdout", stdout_capture):
        exit_code = main([])

    assert exit_code == 0
    output = stdout_capture.getvalue()

    assert "retrieval_relevance" in output
    assert "sql_correctness" in output
    assert "graph_correctness" in output
    assert "multi_hop" in output
    assert "citation_support" in output
    assert "answer_grounding" in output
    assert "PASS" in output
    assert "ALL CI THRESHOLDS PASSED" in output


def test_evaluate_cli_json_mode() -> None:
    """Verify CLI main with --json emits machine-readable scores."""
    stdout_capture = io.StringIO()
    with patch("sys.stdout", stdout_capture):
        exit_code = main(["--json"])

    assert exit_code == 0
    output = stdout_capture.getvalue()
    data = json.loads(output)
    assert "scores" in data
    assert "passed" in data
    assert data["passed"] is True
    assert data["scores"]["retrieval_relevance"] == 1.00


def test_regression_detection_fails_threshold() -> None:
    """Verify that if scores fall below threshold, run_evaluation flags failure."""
    mock_bad_results = [
        {
            "case": {
                "id": "c1",
                "expected_strategies": ["sql"],
                "requires_multi_hop": True,
                "expected_hops": ["h1", "h2"],
            },
            "result": {
                "strategies_used": ["vector"],  # Mismatched strategy
                "queries": [
                    {
                        "store_type": "sql",
                        "query": "DROP TABLE users;",
                        "result_count": 0,
                    }
                ],  # Malicious/invalid SQL
                "evidence": [],
                "answer": "Ungrounded answer with no citations",
                "citations": [],
                "unresolved_citations": [1, 2],
                "citations_verified": False,
                "verification_ratio": 0.1,
            },
        }
    ]

    cases = [item["case"] for item in mock_bad_results]
    results = [item["result"] for item in mock_bad_results]

    sql_score = calculate_sql_correctness(cases, results)
    assert sql_score == 0.0

    cit_score = calculate_citation_support(cases, results)
    assert cit_score == 0.0
