"""Unit tests for VectorStoreService and GraphStoreService protocols (P5-1, N3).

Validates storage modularity, protocol conformance, cosine similarity search,
metadata filtering, graph traversals, read-only Cypher query execution,
and factory resolution.
"""

from collections.abc import Sequence
from typing import Any

import pytest

from backend.app.core.config import Settings
from rag.graph_store import (
    GraphEdge,
    GraphNode,
    GraphStoreService,
    InMemoryGraphStore,
    Neo4jGraphStore,
    get_graph_store,
    reset_graph_store,
)
from rag.vector_store import (
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorChunk,
    VectorSearchResult,
    VectorStoreService,
    get_vector_store,
    reset_vector_store,
)


class TestVectorStoreProtocol:
    """Tests verifying VectorStoreService protocol adherence and functionality."""

    def test_protocol_conformance(self) -> None:
        """Verify InMemoryVectorStore conforms to VectorStoreService protocol at runtime."""
        store = InMemoryVectorStore()
        assert isinstance(store, VectorStoreService)

    def test_chunk_insertion_and_search(self) -> None:
        """Verify insertion of chunks and cosine similarity search ranking."""
        store = InMemoryVectorStore()
        chunks = [
            VectorChunk(
                id="c1",
                text="Postmortem for Payments API outage",
                embedding=[1.0, 0.0, 0.0],
                metadata={"doc_type": "postmortem", "service": "payments-api"},
                locator="doc:postmortem-inc-2031#chunk-1",
            ),
            VectorChunk(
                id="c2",
                text="Architecture decision record for Kafka event bus",
                embedding=[0.0, 1.0, 0.0],
                metadata={"doc_type": "adr", "service": "data-pipeline"},
                locator="doc:adr-002#chunk-1",
            ),
            VectorChunk(
                id="c3",
                text="Payments gateway timeout retry configuration",
                embedding=[0.9, 0.1, 0.0],
                metadata={"doc_type": "runbook", "service": "payments-api"},
                locator="doc:runbook-payments#chunk-1",
            ),
        ]
        store.add_chunks(chunks)

        assert store.count() == 3
        assert store.get_status_detail() == "memory (3 chunks)"

        # Search query vector close to payments-api
        query = [1.0, 0.0, 0.0]
        results = store.search(query, top_k=2)
        assert len(results) == 2
        assert isinstance(results[0], VectorSearchResult)
        assert results[0].id == "c1"
        assert pytest.approx(results[0].score, rel=1e-2) == 1.0
        assert results[1].id == "c3"

        # Attribute and dict-like compatibility
        assert results[0]["id"] == "c1"
        assert "Payments API" in results[0]["text"]

    def test_search_with_metadata_filters(self) -> None:
        """Verify search filters out non-matching chunks."""
        store = InMemoryVectorStore()
        chunks = [
            {
                "id": "c1",
                "text": "Auth policy",
                "embedding": [1.0, 0.0],
                "metadata": {"team": "identity", "year": 2026},
            },
            {
                "id": "c2",
                "text": "Payments policy",
                "embedding": [1.0, 0.0],
                "metadata": {"team": "payments", "year": 2026},
            },
        ]
        store.add_chunks(chunks)

        filtered = store.search([1.0, 0.0], top_k=5, filters={"team": "payments"})
        assert len(filtered) == 1
        assert filtered[0].id == "c2"

    def test_delete_and_clear(self) -> None:
        """Verify chunk deletion and complete clearing."""
        store = InMemoryVectorStore()
        store.add_chunks(
            [{"id": "del-1", "text": "to delete", "embedding": [0.5, 0.5]}]
        )
        assert store.count() == 1

        assert store.delete_chunk("del-1") is True
        assert store.delete_chunk("unknown") is False
        assert store.count() == 0

        store.add_chunks([{"id": "del-2", "text": "temp", "embedding": [0.1, 0.2]}])
        assert store.count() == 1
        store.clear()
        assert store.count() == 0

    def test_health_check(self) -> None:
        """Verify health check response shape."""
        store = InMemoryVectorStore()
        health = store.health_check()
        assert health["status"] == "ok"
        assert health["detail"] == "memory (0 chunks)"

    def test_add_documents_and_similarity_search_aliases(self) -> None:
        """Verify HLD §5.1 method aliases add_documents and similarity_search."""
        store = InMemoryVectorStore()
        store.add_documents(
            [VectorChunk(id="alias-1", text="Alias test", embedding=[0.7, 0.7])]
        )
        assert store.count() == 1
        results = store.similarity_search([0.7, 0.7], k=5)
        assert len(results) == 1
        assert results[0].id == "alias-1"


class TestGraphStoreProtocol:
    """Tests verifying GraphStoreService protocol adherence and graph operations."""

    def test_protocol_conformance(self) -> None:
        """Verify InMemoryGraphStore conforms to GraphStoreService protocol at runtime."""
        store = InMemoryGraphStore()
        assert isinstance(store, GraphStoreService)

    def test_node_and_edge_crud(self) -> None:
        """Verify node/edge addition, retrieval, and status detail."""
        node_model = GraphNode(id="test-n", label="TestLabel", properties={"k": "v"})
        assert node_model.id == "test-n"
        assert node_model["label"] == "TestLabel"
        assert node_model.to_dict()["properties"]["k"] == "v"

        edge_model = GraphEdge(
            source="a", target="b", type="REL", properties={"weight": 1.0}
        )
        assert edge_model.source == "a"
        assert edge_model["type"] == "REL"
        assert edge_model.to_dict()["properties"]["weight"] == 1.0

        store = InMemoryGraphStore()
        store.add_node(
            "svc-payments", "Service", {"tier": "critical", "language": "python"}
        )
        store.add_node("team-payments", "Team", {"lead": "Jane Doe"})
        store.add_edge("team-payments", "svc-payments", "OWNS", {"since": "2024"})

        assert store.node_count() == 2
        assert store.edge_count() == 1
        assert store.get_status_detail() == "memory (2 nodes, 1 edges)"

        node = store.get_node("svc-payments")
        assert node is not None
        assert node["label"] == "Service"
        assert node["properties"]["tier"] == "critical"

    def test_neighbor_resolution(self) -> None:
        """Verify incoming, outgoing, and undirected neighbor lookups."""
        store = InMemoryGraphStore()
        store.add_node("A", "Node")
        store.add_node("B", "Node")
        store.add_node("C", "Node")
        store.add_edge("A", "B", "CONNECTS_TO")
        store.add_edge("C", "A", "DEPENDS_ON")

        neighbors = store.get_neighbors("A")
        assert len(neighbors) == 2

        out_edges = [n for n in neighbors if n["direction"] == "out"]
        in_edges = [n for n in neighbors if n["direction"] == "in"]
        assert len(out_edges) == 1
        assert out_edges[0]["neighbor_id"] == "B"
        assert len(in_edges) == 1
        assert in_edges[0]["neighbor_id"] == "C"

    def test_multi_hop_expansion(self) -> None:
        """Verify breadth-first expansion across multiple hops."""
        store = InMemoryGraphStore()
        store.add_node("cust-1", "Customer", {"name": "Acme Corp"})
        store.add_node("inc-1", "Incident", {"severity": "SEV1"})
        store.add_node("svc-1", "Service", {"name": "Payments API"})

        store.add_edge("cust-1", "inc-1", "IMPACTED_BY")
        store.add_edge("inc-1", "svc-1", "AFFECTED")

        # 1-hop expansion
        hop1 = store.expand("cust-1", max_depth=1)
        assert hop1["root"]["id"] == "cust-1"
        assert len(hop1["nodes"]) == 1
        assert hop1["nodes"][0]["id"] == "inc-1"
        assert len(hop1["edges"]) == 1

        # 2-hop expansion
        hop2 = store.expand("cust-1", max_depth=2)
        assert len(hop2["nodes"]) == 2
        node_ids = {n["id"] for n in hop2["nodes"]}
        assert node_ids == {"inc-1", "svc-1"}
        assert len(hop2["edges"]) == 2

        # Non-existent node expansion returns empty
        assert store.expand("nonexistent") == {"nodes": [], "edges": []}

    def test_read_only_cypher_simulation(self) -> None:
        """Verify simulated Cypher read query and rejection of write mutations."""
        store = InMemoryGraphStore()
        store.add_node("svc-1", "Service", {"name": "Payments API"})
        store.add_node("svc-2", "Service", {"name": "Identity Service"})
        store.add_node("team-1", "Team", {"name": "Payments Platform"})

        # Read query by label
        results = store.query("MATCH (n:Service) RETURN n")
        assert len(results) == 2
        labels = {r["label"] for r in results}
        assert labels == {"Service"}

        # query_read_only alias
        ro_results = store.query_read_only("MATCH (n:Team) RETURN n")
        assert len(ro_results) == 1
        assert ro_results[0]["id"] == "team-1"

        # Write mutations must be rejected under query_read_only
        with pytest.raises(ValueError, match="Read-only violation"):
            store.query_read_only("CREATE (n:BadNode {name: 'Exploit'})")

        with pytest.raises(ValueError, match="Read-only violation"):
            store.query_read_only("MATCH (n:Service) DELETE n")

    def test_typed_traversals(self) -> None:
        """Verify typed domain traversals."""
        store = InMemoryGraphStore()
        store.add_node("cust-10", "Customer", {"name": "Global Retail"})
        store.add_node("inc-2031", "Incident", {"title": "Payments API Outage"})
        store.add_node("svc-pay", "Service", {"name": "Payments API"})
        store.add_node("team-pay", "Team", {"name": "Payments Platform"})

        store.add_edge("cust-10", "inc-2031", "IMPACTED_BY")
        store.add_edge("inc-2031", "svc-pay", "AFFECTED")
        store.add_edge("team-pay", "svc-pay", "OWNS")

        # Traversal: customer_impact
        impact = store.execute_traversal("customer_impact", {"customer_id": "cust-10"})
        assert len(impact) >= 1
        assert any(item.get("id") == "inc-2031" for item in impact)

        # Traversal: team_ownership
        owned = store.execute_traversal("team_ownership", {"team_id": "team-pay"})
        assert len(owned) == 1
        assert owned[0]["id"] == "svc-pay"

    def test_clear_and_health_check(self) -> None:
        """Verify graph clear and health check."""
        store = InMemoryGraphStore()
        store.add_node("n1", "Test")
        store.add_edge("n1", "n1", "SELF")
        assert store.node_count() == 1
        assert store.edge_count() == 1

        store.clear()
        assert store.node_count() == 0
        assert store.edge_count() == 0

        health = store.health_check()
        assert health["status"] == "ok"
        assert health["detail"] == "memory (0 nodes, 0 edges)"


class TestStoreFactories:
    """Tests verifying get_vector_store() and get_graph_store() factory resolution."""

    def test_default_offline_factories(self) -> None:
        """Verify memory backends are resolved under default offline settings."""
        reset_vector_store()
        reset_graph_store()

        settings = Settings(vector_store="memory", graph_store="memory")
        v_store = get_vector_store(settings)
        g_store = get_graph_store(settings)

        assert isinstance(v_store, InMemoryVectorStore)
        assert isinstance(g_store, InMemoryGraphStore)
        assert isinstance(v_store, VectorStoreService)
        assert isinstance(g_store, GraphStoreService)

    def test_qdrant_factory_resolution(self) -> None:
        """Verify Qdrant store resolution for VECTOR_STORE=qdrant."""
        settings = Settings(
            vector_store="qdrant",
            qdrant_url="http://qdrant.internal:6333",
            qdrant_api_key="secret-key",
        )
        store = get_vector_store(settings)
        assert isinstance(store, QdrantVectorStore)
        assert isinstance(store, VectorStoreService)
        health = store.health_check()
        assert health["status"] == "ok"
        assert "qdrant http://qdrant.internal:6333" in health["detail"]

    def test_neo4j_factory_resolution(self) -> None:
        """Verify Neo4j store resolution for GRAPH_STORE=neo4j."""
        settings = Settings(
            graph_store="neo4j",
            neo4j_uri="bolt://neo4j.internal:7687",
            neo4j_user="neo4j",
            neo4j_password="password",
        )
        store = get_graph_store(settings)
        assert isinstance(store, Neo4jGraphStore)
        assert isinstance(store, GraphStoreService)
        health = store.health_check()
        assert health["status"] == "ok"
        assert "neo4j bolt://neo4j.internal:7687" in health["detail"]

    def test_unsupported_factory_raises(self) -> None:
        """Verify unsupported store backends raise descriptive ValueError."""
        bad_vec_settings = Settings(vector_store="unsupported_vec")
        with pytest.raises(
            ValueError, match="Unsupported vector store backend: unsupported_vec"
        ):
            get_vector_store(bad_vec_settings)

        bad_graph_settings = Settings(graph_store="unsupported_graph")
        with pytest.raises(
            ValueError, match="Unsupported graph store backend: unsupported_graph"
        ):
            get_graph_store(bad_graph_settings)


class TestStorageModularityN3:
    """Verify requirement N3: storage modularity via custom protocol implementation."""

    def test_custom_vector_store_satisfies_protocol(self) -> None:
        """Demonstrate that an external/custom vector store conforms to VectorStoreService."""

        class CustomVectorStore:
            def add_chunks(
                self, chunks: Sequence[VectorChunk | dict[str, Any]]
            ) -> None:
                pass

            def add_documents(
                self, documents: Sequence[VectorChunk | dict[str, Any]]
            ) -> None:
                pass

            def search(
                self,
                query_vector: list[float],
                top_k: int = 5,
                filters: dict[str, Any] | None = None,
            ) -> list[VectorSearchResult]:
                return []

            def similarity_search(
                self,
                query_vector: list[float],
                k: int = 10,
                filters: dict[str, Any] | None = None,
            ) -> list[VectorSearchResult]:
                return []

            def count(self) -> int:
                return 0

            def get_status_detail(self) -> str:
                return "custom (0 chunks)"

            def delete_chunk(self, chunk_id: str) -> bool:
                return True

            def clear(self) -> None:
                pass

            def health_check(self) -> dict[str, Any]:
                return {"status": "ok", "detail": "custom vector store"}

        custom = CustomVectorStore()
        assert isinstance(custom, VectorStoreService)
