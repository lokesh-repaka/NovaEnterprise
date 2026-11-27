"""LangGraph research workflow StateGraph engine for NovaEnterprise (P10-1, F1–F12, Claude.md §7.3).

Exposes:
- GRAPH_NODES: Canonical list of exactly 13 workflow nodes in topological execution order.
- GRAPH_EDGES: Directed sequential and conditional edge tuples connecting the 13 nodes.
- route_after_check_missing: Conditional router directing between corrective_retrieval and verify_evidence.
- build_graph: Function assembling and compiling StateGraph(ResearchState) with optional checkpointer.
- get_compiled_graph: Singleton/cached getter returning runnable compiled graph.

Workflow Topology:
  START -> recall_memory -> analyze_query -> assess_complexity -> decompose -> route_retrieval
        -> execute_retrieval -> collect_evidence -> check_missing_evidence
        -[needs_retry==True]-> corrective_retrieval -> (loop back to collect_evidence)
        -[needs_retry==False]-> verify_evidence -> synthesize_answer -> verify_citations
        -> update_memory -> END
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.nodes.analyze_query import analyze_query
from agents.nodes.assess_complexity import assess_complexity
from agents.nodes.check_missing_evidence import check_missing_evidence
from agents.nodes.collect_evidence import collect_evidence
from agents.nodes.corrective_retrieval import corrective_retrieval
from agents.nodes.decompose import decompose
from agents.nodes.execute_retrieval import execute_retrieval
from agents.nodes.recall_memory import recall_memory
from agents.nodes.route_retrieval import route_retrieval
from agents.nodes.synthesize_answer import synthesize_answer
from agents.nodes.update_memory import update_memory
from agents.nodes.verify_citations import verify_citations
from agents.nodes.verify_evidence import verify_evidence
from agents.state import ResearchState

# Canonical list of exactly 13 workflow nodes in topological execution order (Claude.md §7.3, §20)
GRAPH_NODES: list[str] = [
    "recall_memory",
    "analyze_query",
    "assess_complexity",
    "decompose",
    "route_retrieval",
    "execute_retrieval",
    "collect_evidence",
    "check_missing_evidence",
    "corrective_retrieval",
    "verify_evidence",
    "synthesize_answer",
    "verify_citations",
    "update_memory",
]

# Canonical directed edge transitions in the research workflow
GRAPH_EDGES: list[tuple[str, str]] = [
    ("recall_memory", "analyze_query"),
    ("analyze_query", "assess_complexity"),
    ("assess_complexity", "decompose"),
    ("decompose", "route_retrieval"),
    ("route_retrieval", "execute_retrieval"),
    ("execute_retrieval", "collect_evidence"),
    ("collect_evidence", "check_missing_evidence"),
    ("check_missing_evidence", "corrective_retrieval"),
    ("check_missing_evidence", "verify_evidence"),
    ("corrective_retrieval", "collect_evidence"),
    ("verify_evidence", "synthesize_answer"),
    ("synthesize_answer", "verify_citations"),
    ("verify_citations", "update_memory"),
]


def route_after_check_missing(state: ResearchState | dict[str, Any]) -> str:
    """Conditional router determining whether to trigger corrective retrieval or proceed to verification.

    Args:
        state: Current ResearchState or dictionary representation.

    Returns:
        "corrective_retrieval" if state indicates retry is required, else "verify_evidence".
    """
    if isinstance(state, dict):
        needs_retry = bool(state.get("needs_retry", False))
    else:
        needs_retry = bool(getattr(state, "needs_retry", False))

    return "corrective_retrieval" if needs_retry else "verify_evidence"


def build_graph(checkpointer: Any = None) -> Any:
    """Build and compile the 13-node research workflow StateGraph.

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence.

    Returns:
        Compiled StateGraph runnable.
    """
    workflow: Any = StateGraph(ResearchState)

    # 1. Add all 13 canonical nodes
    workflow.add_node("recall_memory", recall_memory)
    workflow.add_node("analyze_query", analyze_query)
    workflow.add_node("assess_complexity", assess_complexity)
    workflow.add_node("decompose", decompose)
    workflow.add_node("route_retrieval", route_retrieval)
    workflow.add_node("execute_retrieval", execute_retrieval)
    workflow.add_node("collect_evidence", collect_evidence)
    workflow.add_node("check_missing_evidence", check_missing_evidence)
    workflow.add_node("corrective_retrieval", corrective_retrieval)
    workflow.add_node("verify_evidence", verify_evidence)
    workflow.add_node("synthesize_answer", synthesize_answer)
    workflow.add_node("verify_citations", verify_citations)
    workflow.add_node("update_memory", update_memory)

    # 2. Add sequential transitions
    workflow.add_edge(START, "recall_memory")
    workflow.add_edge("recall_memory", "analyze_query")
    workflow.add_edge("analyze_query", "assess_complexity")
    workflow.add_edge("assess_complexity", "decompose")
    workflow.add_edge("decompose", "route_retrieval")
    workflow.add_edge("route_retrieval", "execute_retrieval")
    workflow.add_edge("execute_retrieval", "collect_evidence")
    workflow.add_edge("collect_evidence", "check_missing_evidence")

    # 3. Add conditional edge from check_missing_evidence
    workflow.add_conditional_edges(
        "check_missing_evidence",
        route_after_check_missing,
        {
            "corrective_retrieval": "corrective_retrieval",
            "verify_evidence": "verify_evidence",
        },
    )

    # 4. Corrective loop edge back to collect_evidence
    workflow.add_edge("corrective_retrieval", "collect_evidence")

    # 5. Verification and synthesis sequential edges
    workflow.add_edge("verify_evidence", "synthesize_answer")
    workflow.add_edge("synthesize_answer", "verify_citations")
    workflow.add_edge("verify_citations", "update_memory")
    workflow.add_edge("update_memory", END)

    return workflow.compile(checkpointer=checkpointer)


# Singleton instance of compiled StateGraph
_COMPILED_GRAPH: Any = None


def get_compiled_graph() -> Any:
    """Return a singleton or cached instance of the compiled StateGraph."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_graph()
    return _COMPILED_GRAPH


__all__ = [
    "GRAPH_EDGES",
    "GRAPH_NODES",
    "build_graph",
    "get_compiled_graph",
    "route_after_check_missing",
]
