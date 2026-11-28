"""Knowledge graph explorer, expansion, and read-only Cypher query service (P11-1, F14, Claude.md §8, §18.1).

Encapsulates property graph access, node neighborhood traversal, and secure read-only Cypher execution.
"""

from __future__ import annotations

import time
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.schemas.graph import (
    CypherQueryResponse,
    GraphDataResponse,
    GraphEdgeResponse,
    GraphNodeResponse,
)
from rag.graph_retrieval import validate_cypher
from rag.graph_store import GraphStoreService, get_graph_store

logger = get_logger("services.graph")


def _format_node(node_dict: dict[str, Any]) -> GraphNodeResponse:
    """Format raw node dictionary into GraphNodeResponse model."""
    return GraphNodeResponse(
        id=str(node_dict.get("id", "")),
        label=str(node_dict.get("label", "Unknown")),
        properties=dict(node_dict.get("properties", {})),
    )


def _format_edge(edge_dict: dict[str, Any], idx: int = 0) -> GraphEdgeResponse:
    """Format raw edge dictionary into GraphEdgeResponse model."""
    source = str(edge_dict.get("source", ""))
    target = str(edge_dict.get("target", ""))
    rel_type = str(edge_dict.get("type", "RELATED_TO"))
    edge_id = edge_dict.get("id") or f"{source}-{rel_type}-{target}"
    return GraphEdgeResponse(
        id=str(edge_id),
        source=source,
        target=target,
        type=rel_type,
        properties=dict(edge_dict.get("properties", {})),
    )


class GraphService:
    """Service providing knowledge graph subgraph querying, node expansion, and Cypher execution."""

    def __init__(self, store: GraphStoreService | None = None) -> None:
        self._store: GraphStoreService = store or get_graph_store()

    def get_subgraph(
        self, limit: int = 100, node_label: str | None = None
    ) -> GraphDataResponse:
        """Browse graph entities, optionally filtered by node label, bounded by limit."""
        all_nodes = self._store.get_all_nodes()

        # Filter by label if requested
        if node_label:
            target_label = node_label.strip().lower()
            filtered_nodes = [
                n for n in all_nodes if str(n.get("label", "")).lower() == target_label
            ]
        else:
            filtered_nodes = all_nodes

        # Apply limit to nodes
        selected_nodes = filtered_nodes[:limit]
        node_ids = {n.get("id") for n in selected_nodes if n.get("id")}

        # Find connecting edges for the selected nodes
        all_edges = self._store.get_all_edges()
        connecting_edges: list[dict[str, Any]] = []
        for e in all_edges:
            if e.get("source") in node_ids and e.get("target") in node_ids:
                connecting_edges.append(e)
                if len(connecting_edges) >= limit:
                    break

        formatted_nodes = [_format_node(n) for n in selected_nodes]
        formatted_edges = [
            _format_edge(e, idx) for idx, e in enumerate(connecting_edges)
        ]

        logger.info(
            "Retrieved subgraph (label=%s, limit=%d): %d nodes, %d edges",
            node_label,
            limit,
            len(formatted_nodes),
            len(formatted_edges),
        )
        return GraphDataResponse(
            nodes=formatted_nodes,
            edges=formatted_edges,
            root=None,
        )

    def expand_node(
        self,
        node_id: str,
        direction: str = "both",
        relationship_type: str | None = None,
    ) -> GraphDataResponse | None:
        """Expand a single node by retrieving all 1-hop neighbor nodes and connecting edges (F14)."""
        root_raw = self._store.get_node(node_id)
        if root_raw is None:
            logger.warning("Node '%s' not found for expansion", node_id)
            return None

        root_node = _format_node(root_raw)
        norm_direction = direction.lower()
        rel_filter = relationship_type.strip().upper() if relationship_type else None

        all_edges = self._store.get_all_edges()
        matching_edges: list[dict[str, Any]] = []
        neighbor_ids: set[str] = set()

        for edge in all_edges:
            src = edge.get("source")
            tgt = edge.get("target")
            etype = str(edge.get("type", "")).upper()

            # Filter relationship type if provided
            if rel_filter and etype != rel_filter:
                continue

            # Evaluate direction
            matches = False
            if norm_direction == "out" and src == node_id:
                matches = True
                if tgt:
                    neighbor_ids.add(tgt)
            elif norm_direction == "in" and tgt == node_id:
                matches = True
                if src:
                    neighbor_ids.add(src)
            elif norm_direction == "both":
                if src == node_id:
                    matches = True
                    if tgt:
                        neighbor_ids.add(tgt)
                elif tgt == node_id:
                    matches = True
                    if src:
                        neighbor_ids.add(src)

            if matches:
                matching_edges.append(edge)

        # Retrieve neighbor node records
        neighbor_nodes: list[GraphNodeResponse] = []
        for nid in sorted(neighbor_ids):
            if nid != node_id:
                n_raw = self._store.get_node(nid)
                if n_raw:
                    neighbor_nodes.append(_format_node(n_raw))

        formatted_edges = [_format_edge(e, idx) for idx, e in enumerate(matching_edges)]

        # Combine root and neighbors for visual canvas rendering
        all_graph_nodes = [root_node] + neighbor_nodes

        logger.info(
            "Expanded node '%s' (dir=%s, rel=%s): %d neighbors, %d edges",
            node_id,
            direction,
            relationship_type,
            len(neighbor_nodes),
            len(formatted_edges),
        )

        return GraphDataResponse(
            nodes=all_graph_nodes,
            edges=formatted_edges,
            root=root_node,
        )

    def execute_cypher(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> CypherQueryResponse:
        """Execute a validated read-only Cypher query with strict AST mutation guards (F14, Claude.md §18.1)."""
        # 1. Enforce strict Cypher read-only AST validation
        if not validate_cypher(query):
            logger.warning("Rejected invalid/mutating Cypher query: %s", query[:80])
            raise ValueError(
                "Invalid Cypher query: must be a single read-only MATCH...RETURN statement. "
                "Write mutations, semicolon chaining, and administrative procedures are prohibited."
            )

        start_time = time.perf_counter()
        raw_results = self._store.query_read_only(query, parameters)
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Extract any node or edge entities present in query output
        extracted_nodes: list[GraphNodeResponse] = []
        extracted_edges: list[GraphEdgeResponse] = []

        for item in raw_results:
            if isinstance(item, dict):
                # If item resembles a node (has id and label)
                if "id" in item and "label" in item:
                    extracted_nodes.append(_format_node(item))
                elif "source" in item and "target" in item and "type" in item:
                    extracted_edges.append(_format_edge(item))

        logger.info(
            "Executed Cypher query in %.2f ms (%d rows returned)",
            execution_time_ms,
            len(raw_results),
        )

        return CypherQueryResponse(
            results=raw_results,
            execution_time_ms=execution_time_ms,
            nodes=extracted_nodes,
            edges=extracted_edges,
        )


# Singleton instance
_graph_service_instance: GraphService | None = None


def get_graph_service(store: GraphStoreService | None = None) -> GraphService:
    """Factory retrieving or initializing the GraphService singleton."""
    global _graph_service_instance
    if _graph_service_instance is None or store is not None:
        _graph_service_instance = GraphService(store=store)
    return _graph_service_instance


def reset_graph_service() -> None:
    """Reset GraphService singleton for isolated testing."""
    global _graph_service_instance
    _graph_service_instance = None


__all__ = [
    "GraphService",
    "get_graph_service",
    "reset_graph_service",
]
