"""NovaEnterprise Evaluation and CI Threshold Metrics Suite (P14-1, Claude.md §3.3, §14)."""

from typing import Any

from tests.evaluation.metrics import (
    calculate_answer_grounding,
    calculate_citation_support,
    calculate_graph_correctness,
    calculate_multi_hop_coverage,
    calculate_retrieval_relevance,
    calculate_sql_correctness,
)


def __getattr__(name: str) -> Any:
    """Lazy-load evaluation runner components to avoid cyclic import warnings when run via -m."""
    if name in ("CI_THRESHOLDS", "main", "run_evaluation"):
        import tests.evaluation.evaluate as ev

        return getattr(ev, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CI_THRESHOLDS",
    "calculate_answer_grounding",
    "calculate_citation_support",
    "calculate_graph_correctness",
    "calculate_multi_hop_coverage",
    "calculate_retrieval_relevance",
    "calculate_sql_correctness",
    "main",
    "run_evaluation",
]
