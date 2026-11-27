"""In-memory mock stores for offline Vector and Graph RAG operations (N1, N3).

Provides pure Python in-memory storage, vector similarity search, and graph traversal
without requiring Qdrant or Neo4j daemon processes.
"""

import math
from collections import deque
from typing import Any


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return max(-1.0, min(1.0, dot_product / (norm_a * norm_b)))


class InMemoryVectorStore:
    """In-memory vector store supporting cosine similarity ranking and metadata filtering."""

    def __init__(self) -> None:
        self._chunks: dict[str, dict[str, Any]] = {}

    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Add or update document chunks in the store."""
        for chunk in chunks:
            chunk_id = str(chunk.get("id"))
            self._chunks[chunk_id] = {
                "id": chunk_id,
                "text": chunk.get("text", ""),
                "embedding": list(chunk.get("embedding", [])),
                "metadata": dict(chunk.get("metadata", {})),
            }

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search top-k most similar chunks using cosine similarity with optional metadata filters."""
        scored: list[dict[str, Any]] = []

        for chunk_id, chunk in self._chunks.items():
            # Check metadata filters
            if filters:
                meta = chunk.get("metadata", {})
                matches = all(meta.get(k) == v for k, v in filters.items())
                if not matches:
                    continue

            emb = chunk.get("embedding", [])
            score = _cosine_similarity(query_vector, emb)
            scored.append(
                {
                    "id": chunk_id,
                    "text": chunk.get("text", ""),
                    "score": round(score, 4),
                    "metadata": chunk.get("metadata", {}),
                }
            )

        # Sort descending by similarity score
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        """Return the total number of chunks currently indexed."""
        return len(self._chunks)

    def get_status_detail(self) -> str:
        """Return formatted status detail matching Claude.md §10."""
        return f"memory ({self.count()} chunks)"

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete a single chunk by ID."""
        if chunk_id in self._chunks:
            del self._chunks[chunk_id]
            return True
        return False

    def clear(self) -> None:
        """Remove all chunks from memory."""
        self._chunks.clear()


class InMemoryGraphStore:
    """In-memory property graph store supporting node lookup, expansion, and traversals."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []

    def add_node(
        self, node_id: str, label: str, properties: dict[str, Any] | None = None
    ) -> None:
        """Add or update an entity node."""
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
        """Add a directed relationship between two nodes."""
        self._edges.append(
            {
                "source": source,
                "target": target,
                "type": rel_type,
                "properties": dict(properties or {}),
            }
        )

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve a node by its unique ID."""
        return self._nodes.get(node_id)

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

        # Queue contains (current_node_id, depth)
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

        # Exclude root node from result nodes list or include it
        result_nodes = [self._nodes[nid] for nid in visited_nodes if nid != node_id]
        return {
            "root": self._nodes[node_id],
            "nodes": result_nodes,
            "edges": discovered_edges,
        }

    def query(
        self, cypher_like: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Simulate basic Cypher label/property matching queries for offline testing."""
        results: list[dict[str, Any]] = []
        query_upper = cypher_like.upper()

        # Simulated MATCH by label e.g., "MATCH (n:Service)"
        for node in self._nodes.values():
            label = node.get("label", "")
            if f":{label.upper()}" in query_upper or f":{label}" in cypher_like:
                results.append(node)

        return results

    def clear(self) -> None:
        """Clear all nodes and edges from memory."""
        self._nodes.clear()
        self._edges.clear()
