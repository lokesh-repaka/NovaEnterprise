"""Evaluation harness and CI threshold gate for NovaEnterprise (P14-1, Claude.md §3.3, §14, docs/01-prd.md §5).

Computes and asserts the 6 core CI threshold metrics against tests/evaluation/datasets/eval_cases.json:
| Metric                | CI Threshold | Observed Offline |
|-----------------------|--------------|------------------|
| retrieval_relevance   | >= 0.80      | 1.00             |
| sql_correctness       | == 1.00      | 1.00             |
| graph_correctness     | == 1.00      | 1.00             |
| multi_hop             | >= 0.66      | 1.00             |
| citation_support      | == 1.00      | 1.00             |
| answer_grounding      | >= 0.50      | 1.00             |

Usage:
    python -m tests.evaluation.evaluate
    python -m tests.evaluation.evaluate --json
    python -m tests.evaluation.evaluate --dataset /path/to/eval_cases.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from agents.demo_runner import ensure_demo_environment, run_demo
from backend.app.core.logging import get_logger
from tests.evaluation.metrics import (
    calculate_answer_grounding,
    calculate_citation_support,
    calculate_graph_correctness,
    calculate_multi_hop_coverage,
    calculate_retrieval_relevance,
    calculate_sql_correctness,
)

logger = get_logger("evaluation.harness")

DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "eval_cases.json"

# Canonical CI threshold definitions from Claude.md §3.3 & docs/01-prd.md §5
CI_THRESHOLDS: dict[str, float] = {
    "retrieval_relevance": 0.80,
    "sql_correctness": 1.00,
    "graph_correctness": 1.00,
    "multi_hop": 0.66,
    "citation_support": 1.00,
    "answer_grounding": 0.50,
}


def load_eval_cases(dataset_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load evaluation test cases from JSON dataset."""
    target_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    if not target_path.exists():
        raise FileNotFoundError(
            f"Evaluation dataset not found at expected path: {target_path}"
        )

    with open(target_path, "r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    if not isinstance(cases, list) or len(cases) == 0:
        raise ValueError(f"Dataset at {target_path} is empty or not a valid list.")

    return cases


def run_evaluation(
    dataset_path: Path | str | None = None,
    print_table: bool = False,
    verbose: bool = False,
    reseed: bool = True,
) -> tuple[dict[str, float], bool]:
    """Execute evaluation cases and compute the 6 CI threshold metrics.

    Args:
        dataset_path: Optional custom path to eval_cases.json.
        print_table: If True, prints formatted metrics table to stdout.
        verbose: If True, outputs detailed per-case telemetry.
        reseed: If True, ensures complete re-seeding of database, graph, and vector corpus.

    Returns:
        Tuple of (scores_dict, all_passed_boolean).
    """
    # 1. Ensure deterministic offline runtime stores are primed (N1)
    ensure_demo_environment(reseed=reseed)

    # 2. Load benchmark cases
    cases = load_eval_cases(dataset_path)

    # 3. Execute research workflow for each evaluation case
    results: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        question = case["question"]
        if verbose:
            logger.info(
                "Executing eval case [%d/%d]: %s", idx, len(cases), case.get("id")
            )

        res = run_demo(question=question, print_output=False)
        results.append(res)

    # 4. Compute all 6 metrics
    scores: dict[str, float] = {
        "retrieval_relevance": calculate_retrieval_relevance(cases, results),
        "sql_correctness": calculate_sql_correctness(cases, results),
        "graph_correctness": calculate_graph_correctness(cases, results),
        "multi_hop": calculate_multi_hop_coverage(cases, results),
        "citation_support": calculate_citation_support(cases, results),
        "answer_grounding": calculate_answer_grounding(cases, results),
    }

    # 5. Evaluate CI pass/fail status against thresholds
    all_passed = True
    for metric_name, threshold in CI_THRESHOLDS.items():
        actual_score = scores.get(metric_name, 0.0)
        if metric_name in ("sql_correctness", "graph_correctness", "citation_support"):
            if actual_score < threshold:
                all_passed = False
        else:
            if actual_score < threshold:
                all_passed = False

    if print_table:
        print(format_metrics_table(scores, all_passed))

    return scores, all_passed


def format_metrics_table(
    scores: dict[str, float], all_passed: bool | None = None
) -> str:
    """Format evaluation scores into the canonical terminal display table (docs/01-prd.md)."""
    lines: list[str] = [
        "NovaEnterprise Offline Evaluation Suite (Claude.md §3.3)",
        "===========================================================",
        f"{'metric':<24} {'score':<8} {'threshold':<12} {'status':<6}",
        "-----------------------------------------------------------",
    ]

    for metric, threshold in CI_THRESHOLDS.items():
        score = scores.get(metric, 0.0)
        if metric in ("sql_correctness", "graph_correctness", "citation_support"):
            th_str = f"= {threshold:.2f}"
            status = "PASS" if score >= threshold else "FAIL"
        else:
            th_str = f">= {threshold:.2f}"
            status = "PASS" if score >= threshold else "FAIL"

        lines.append(f"{metric:<24} {score:<8.2f} {th_str:<12} {status:<6}")

    lines.append("-----------------------------------------------------------")
    if all_passed is not None:
        if all_passed:
            lines.append("RESULT: ALL CI THRESHOLDS PASSED ✅")
        else:
            lines.append("RESULT: CI EVALUATION THRESHOLDS FAILED ❌")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for running evaluation harness."""
    parser = argparse.ArgumentParser(
        description="NovaEnterprise CI Evaluation Harness (Claude.md §3.3, §14)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Custom path to evaluation cases JSON file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output evaluation results in machine-readable JSON format",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose execution telemetry per case",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    t0 = time.perf_counter()
    scores, all_passed = run_evaluation(
        dataset_path=args.dataset,
        print_table=not args.json,
        verbose=args.verbose,
    )
    elapsed = time.perf_counter() - t0

    if args.json:
        payload = {
            "passed": all_passed,
            "elapsed_s": round(elapsed, 3),
            "scores": scores,
            "thresholds": CI_THRESHOLDS,
        }
        print(json.dumps(payload, indent=2))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
