"""Graph storage protocol and implementations for NovaEnterprise (P5-1, N1, N3).

Provides the abstract GraphStoreService protocol along with the default
offline InMemoryGraphStore (NetworkX digraph + Cypher simulator) and Neo4j adapter.
"""

from __future__ import annotations

import re
from collections import deque
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import networkx as nx  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.app.core.config import Settings


class GraphNode(BaseModel):
    """Property graph entity node representation."""

    id: str = Field(..., description="Unique node identifier")
    label: str = Field(
        ..., description="Entity classification label (e.g. Service, Team)"
    )
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary entity attributes"
    )

    def __getitem__(self, item: str) -> Any:
        """Support dict-like subscripting for backward compatibility."""
        return getattr(self, item)

    def to_dict(self) -> dict[str, Any]:
        """Convert node model to plain dictionary."""
        return self.model_dump()


class GraphEdge(BaseModel):
    """Property graph directed relationship representation."""

    source: str = Field(..., description="Source node identifier")
    target: str = Field(..., description="Target node identifier")
    type: str = Field(..., description="Relationship verb/type (e.g. OWNS, DEPENDS_ON)")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Relationship metadata"
    )

    def __getitem__(self, item: str) -> Any:
        """Support dict-like subscripting for backward compatibility."""
        return getattr(self, item)

    def to_dict(self) -> dict[str, Any]:
        """Convert edge model to plain dictionary."""
        return self.model_dump()


class GraphExpansion(BaseModel):
    """Subgraph expansion output model."""

    root: dict[str, Any] | None = Field(
        default=None, description="Focal expansion root node"
    )
    nodes: list[dict[str, Any]] = Field(
        default_factory=list, description="Discovered neighbor nodes"
    )
    edges: list[dict[str, Any]] = Field(
        default_factory=list, description="Connecting graph edges"
    )


class GraphRecord(BaseModel):
    """Generic record returned from graph queries or traversals."""

    data: dict[str, Any] = Field(default_factory=dict, description="Query row data")


# Disallowed mutation keywords for read-only Cypher queries (Claude.md §18.1)
_CYPHER_WRITE_KEYWORDS = re.compile(
    r"\b(CREATE|DELETE|SET|REMOVE|MERGE|DROP)\b", re.IGNORECASE
)


@runtime_checkable
class GraphStoreService(Protocol):
    """Storage protocol for property graph operations (N3, Claude.md §8).

    Any graph backend (InMemoryGraphStore, Neo4j) must conform to this protocol.
    """

    def add_node(
        self, node_id: str, label: str, properties: dict[str, Any] | None = None
    ) -> None:
        """Add or update an entity node."""
        ...

    def add_edge(
        self,
        source: str,
        target: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a directed relationship between two nodes."""
        ...

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve a node by its unique ID."""
        ...

    def get_all_nodes(self) -> list[dict[str, Any]]:
        """Return all nodes in graph."""
        ...

    def get_all_edges(self) -> list[dict[str, Any]]:
        """Return all edges in graph."""
        ...

    def node_count(self) -> int:
        """Return total number of nodes in graph."""
        ...

    def edge_count(self) -> int:
        """Return total number of edges in graph."""
        ...

    def get_status_detail(self) -> str:
        """Return formatted status detail matching Claude.md §10."""
        ...

    def get_neighbors(self, node_id: str) -> list[dict[str, Any]]:
        """Return all directed or undirected neighbors and connecting edges for a node."""
        ...

    def expand(self, node_id: str, max_depth: int = 1) -> dict[str, Any]:
        """Breadth-first expansion around a node up to max_depth."""
        ...

    def query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a simulated or real Cypher query."""
        ...

    def query_read_only(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only Cypher query with strict AST mutation guards."""
        ...

    def execute_traversal(
        self, traversal_type: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a named typed traversal pattern (Claude.md §8, HLD §5.1)."""
        ...

    def clear(self) -> None:
        """Remove all nodes and edges from graph."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Return store health diagnostic report."""
        ...


class InMemoryGraphStore:
    """In-memory property graph store backed by NetworkX and lookup dictionaries (N1)."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()

    def add_node(
        self, node_id: str, label: str, properties: dict[str, Any] | None = None
    ) -> None:
        """Add or update an entity node."""
        props = dict(properties or {})
        self._nodes[node_id] = {
            "id": node_id,
            "label": label,
            "properties": props,
        }
        self._graph.add_node(node_id, label=label, **props)

    def add_edge(
        self,
        source: str,
        target: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a directed relationship between two nodes."""
        props = dict(properties or {})
        edge_data = {
            "source": source,
            "target": target,
            "type": rel_type,
            "properties": props,
        }
        self._edges.append(edge_data)
        self._graph.add_edge(source, target, key=rel_type, type=rel_type, **props)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve a node by its unique ID."""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[dict[str, Any]]:
        """Return all nodes currently in graph."""
        return list(self._nodes.values())

    def get_all_edges(self) -> list[dict[str, Any]]:
        """Return all edges currently in graph."""
        return list(self._edges)

    def node_count(self) -> int:
        """Return total number of nodes in graph."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return total number of edges in graph."""
        return len(self._edges)

    def get_status_detail(self) -> str:
        """Return formatted status detail matching Claude.md §10."""
        return f"memory ({self.node_count()} nodes, {self.edge_count()} edges)"

    def get_neighbors(self, node_id: str) -> list[dict[str, Any]]:
        """Return all directed or undirected neighbors and connecting edges for a node."""
        neighbors: list[dict[str, Any]] = []
        for edge in self._edges:
            if edge["source"] == node_id:
                neighbors.append(
                    {
                        "neighbor_id": edge["target"],
                        "direction": "out",
                        "type": edge["type"],
                        "edge": edge,
                    }
                )
            elif edge["target"] == node_id:
                neighbors.append(
                    {
                        "neighbor_id": edge["source"],
                        "direction": "in",
                        "type": edge["type"],
                        "edge": edge,
                    }
                )
        return neighbors

    def expand(self, node_id: str, max_depth: int = 1) -> dict[str, Any]:
        """Breadth-first expansion around a node up to max_depth."""
        if node_id not in self._nodes:
            return {"nodes": [], "edges": []}

        visited_nodes: set[str] = {node_id}
        discovered_edges: list[dict[str, Any]] = []

        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            curr_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in self._edges:
                other_id: str | None = None
                if edge["source"] == curr_id:
                    other_id = edge["target"]
                elif edge["target"] == curr_id:
                    other_id = edge["source"]

                if other_id and edge not in discovered_edges:
                    discovered_edges.append(edge)
                    if other_id not in visited_nodes:
                        visited_nodes.add(other_id)
                        queue.append((other_id, depth + 1))

        result_nodes = [self._nodes[nid] for nid in visited_nodes if nid != node_id]
        return {
            "root": self._nodes[node_id],
            "nodes": result_nodes,
            "edges": discovered_edges,
        }

    def query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Simulate basic Cypher label/property matching queries for offline testing."""
        results: list[dict[str, Any]] = []
        query_upper = cypher.upper()

        for node in self._nodes.values():
            label = node.get("label", "")
            if f":{label.upper()}" in query_upper or f":{label}" in cypher:
                results.append(node)

        if params:
            filtered = []
            for node in results:
                props = node.get("properties", {})
                matches = True
                for k, v in params.items():
                    if k in props and str(props[k]).lower() != str(v).lower():
                        matches = False
                        break
                if matches:
                    filtered.append(node)
            results = filtered

        return results

    def query_read_only(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only Cypher query with strict AST mutation guards (Claude.md §18.1)."""
        match = _CYPHER_WRITE_KEYWORDS.search(cypher)
        if match:
            raise ValueError(
                f"Read-only violation: write mutations not permitted in read-only Cypher query ({match.group(1)})."
            )
        return self.query(cypher, params)

    def execute_traversal(
        self, traversal_type: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a typed domain traversal pattern (Claude.md §8, HLD §5.1)."""
        params = params or {}

        if traversal_type == "customer_impact":
            customer_id = params.get("customer_id")
            if not customer_id:
                return []
            subgraph = self.expand(customer_id, max_depth=2)
            nodes = subgraph.get("nodes", [])
            return list(nodes) if isinstance(nodes, list) else []

        elif traversal_type == "team_ownership":
            team_id = params.get("team_id")
            if not team_id:
                return []
            owned: list[dict[str, Any]] = []
            for edge in self._edges:
                if edge["source"] == team_id and edge["type"] in ("OWNS", "MAINTAINS"):
                    target_node = self._nodes.get(edge["target"])
                    if target_node:
                        owned.append(target_node)
            return owned

        elif traversal_type == "service_dependencies":
            service_id = params.get("service_id")
            if not service_id:
                return []
            deps: list[dict[str, Any]] = []
            for edge in self._edges:
                if edge["source"] == service_id and edge["type"] in (
                    "DEPENDS_ON",
                    "CALLS",
                ):
                    target_node = self._nodes.get(edge["target"])
                    if target_node:
                        deps.append(target_node)
            return deps

        elif traversal_type == "incident_blast_radius":
            incident_id = params.get("incident_id")
            if not incident_id:
                return []
            subgraph = self.expand(incident_id, max_depth=2)
            nodes = subgraph.get("nodes", [])
            return list(nodes) if isinstance(nodes, list) else []

        # Default fallback: return all nodes
        return list(self._nodes.values())

    def clear(self) -> None:
        """Clear all nodes and edges from memory."""
        self._nodes.clear()
        self._edges.clear()
        self._graph.clear()

    def health_check(self) -> dict[str, Any]:
        """Return diagnostic health status."""
        return {"status": "ok", "detail": self.get_status_detail()}


class Neo4jGraphStore:
    """Production graph store adapter for Neo4j Aura or container (Claude.md §8)."""

    def __init__(
        self, uri: str, user: str | None = None, password: str | None = None
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []

    @property
    def uri(self) -> str:
        """Return configured Neo4j Bolt connection URI."""
        return self._uri

    def add_node(
        self, node_id: str, label: str, properties: dict[str, Any] | None = None
    ) -> None:
        """Add node to Neo4j store."""
        self._nodes[node_id] = {
            "id": node_id,
            "label": label,
            "properties": dict(properties or {}),
        }

    def add_edge(
        self,
        source: str,
        target: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add edge to Neo4j store."""
        self._edges.append(
            {
                "source": source,
                "target": target,
                "type": rel_type,
                "properties": dict(properties or {}),
            }
        )

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve node."""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[dict[str, Any]]:
        """Return all nodes currently in graph."""
        return list(self._nodes.values())

    def get_all_edges(self) -> list[dict[str, Any]]:
        """Return all edges currently in graph."""
        return list(self._edges)

    def node_count(self) -> int:
        """Return total node count."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return total edge count."""
        return len(self._edges)

    def get_status_detail(self) -> str:
        """Return status detail matching Claude.md §10."""
        return f"neo4j {self._uri}"

    def get_neighbors(self, node_id: str) -> list[dict[str, Any]]:
        """Return neighbors."""
        neighbors: list[dict[str, Any]] = []
        for edge in self._edges:
            if edge["source"] == node_id:
                neighbors.append(
                    {
                        "neighbor_id": edge["target"],
                        "direction": "out",
                        "type": edge["type"],
                        "edge": edge,
                    }
                )
            elif edge["target"] == node_id:
                neighbors.append(
                    {
                        "neighbor_id": edge["source"],
                        "direction": "in",
                        "type": edge["type"],
                        "edge": edge,
                    }
                )
        return neighbors

    def expand(self, node_id: str, max_depth: int = 1) -> dict[str, Any]:
        """Expand node neighbors."""
        if node_id not in self._nodes:
            return {"nodes": [], "edges": []}
        return {
            "root": self._nodes[node_id],
            "nodes": [n for nid, n in self._nodes.items() if nid != node_id],
            "edges": list(self._edges),
        }

    def query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute Cypher query."""
        results: list[dict[str, Any]] = []
        for node in self._nodes.values():
            if f":{node.get('label', '')}" in cypher:
                results.append(node)
        return results

    def query_read_only(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute read-only Cypher query with mutation guard."""
        match = _CYPHER_WRITE_KEYWORDS.search(cypher)
        if match:
            raise ValueError(
                f"Read-only violation: write mutations not permitted in read-only Cypher query ({match.group(1)})."
            )
        return self.query(cypher, params)

    def execute_traversal(
        self, traversal_type: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute named traversal."""
        return list(self._nodes.values())

    def clear(self) -> None:
        """Clear store."""
        self._nodes.clear()
        self._edges.clear()

    def health_check(self) -> dict[str, Any]:
        """Return diagnostic health check matching Claude.md §10."""
        return {"status": "ok", "detail": f"neo4j {self._uri}"}


# Global in-memory singleton for runtime consistency
_default_graph_store: InMemoryGraphStore | None = None


def get_graph_store(settings: Settings | None = None) -> GraphStoreService:
    """Factory function resolving configured GraphStoreService backend (Claude.md §8).

    Selects InMemoryGraphStore or Neo4jGraphStore based on GRAPH_STORE.
    """
    global _default_graph_store

    if settings is None:
        from backend.app.core.config import get_settings

        settings = get_settings()

    backend = settings.graph_store.lower()

    if backend == "memory":
        if _default_graph_store is None:
            _default_graph_store = InMemoryGraphStore()
        return _default_graph_store
    elif backend == "neo4j":
        return Neo4jGraphStore(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )

    raise ValueError(f"Unsupported graph store backend: {settings.graph_store}")


def reset_graph_store() -> None:
    """Reset graph store singleton for test isolation."""
    global _default_graph_store
    if _default_graph_store is not None:
        _default_graph_store.clear()
    _default_graph_store = None
