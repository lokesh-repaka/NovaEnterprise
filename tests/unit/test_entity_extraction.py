"""Unit tests for entity and relationship extraction (P5-3, F13).

Validates enterprise domain entity recognition (Service, Incident, Customer, Team, ADR, Employee),
typed relationship extraction (AFFECTED, IMPACTED, OWNS, ADDRESSED_BY, DEPENDS_ON),
and knowledge graph indexing.
"""

from pathlib import Path

from rag.chunker import SemanticChunker
from rag.extractor import (
    EntityRelationshipExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from rag.graph_store import GraphEdge, GraphNode, InMemoryGraphStore
from rag.parser import DocumentParser


class TestEntityExtraction:
    """Tests for domain entity identification from unstructured technical text."""

    def test_extract_core_entities_from_structured_postmortem(self) -> None:
        """Verify extraction of Incident, Service, Team, and Customer entities."""
        text = """# Incident Postmortem: INC-2031 Payments API Latency Spike & Outage

**Incident Reference:** INC-2031
**Severity:** SEV1
**Target Service:** Payments API (`svc-payments-api`)
**Owning Team:** Payments Platform (`team-payments`)

## Executive Summary
PostgreSQL database connection pool exhaustion triggered by transaction surge from Acme Corp (cust-acme).
Globex Corp (cust-globex) and Wayne Enterprises (cust-wayne) suffered disruption.
Permanent corrective decision adopted under ADR-042 (Adopt PgBouncer for Connection Pooling).
Lead Investigator: Alice Chen.
"""
        extractor = EntityRelationshipExtractor()
        result = extractor.extract_from_text(text, doc_id="postmortem-inc-2031")

        assert isinstance(result, ExtractionResult)
        assert len(result.entities) >= 5

        entity_ids = {e.id for e in result.entities}
        assert "inc-2031" in entity_ids
        assert "svc-payments-api" in entity_ids
        assert "team-payments" in entity_ids
        assert "cust-acme" in entity_ids
        assert "dec-adr-042" in entity_ids or "adr-042" in entity_ids

        # Check entity model conversion to GraphNode
        service_entity = next(e for e in result.entities if "svc-payments-api" in e.id)
        assert isinstance(service_entity, ExtractedEntity)
        graph_node = service_entity.to_graph_node()
        assert isinstance(graph_node, GraphNode)
        assert graph_node.label == "Service"
        assert graph_node.id == "svc-payments-api"

    def test_extract_relationships(self) -> None:
        """Verify extraction of typed relationships between extracted entities."""
        text = """Incident INC-2031 affected Payments API.
Acme Corp was impacted by incident INC-2031.
Payments Platform owns Payments API.
Incident INC-2031 was addressed by ADR-042.
"""
        extractor = EntityRelationshipExtractor()
        result = extractor.extract_from_text(text, doc_id="doc-test-1")

        assert len(result.relationships) >= 3

        rel_signatures = {
            (r.source_id, r.type, r.target_id) for r in result.relationships
        }

        # Check known edge patterns
        has_affected = any(
            r.type in ("AFFECTED", "AFFECTS")
            and "inc-2031" in r.source_id
            and "payments" in r.target_id
            for r in result.relationships
        )
        assert has_affected, f"Expected AFFECTED edge in {rel_signatures}"

        has_impacted = any(
            r.type in ("IMPACTED", "IMPACTS")
            and "inc-2031" in r.source_id
            and "acme" in r.target_id
            for r in result.relationships
        )
        assert has_impacted, f"Expected IMPACTED edge in {rel_signatures}"

        # Test GraphEdge conversion
        first_rel = result.relationships[0]
        assert isinstance(first_rel, ExtractedRelationship)
        graph_edge = first_rel.to_graph_edge()
        assert isinstance(graph_edge, GraphEdge)
        assert graph_edge.type == first_rel.type

    def test_indexing_into_graph_store(self) -> None:
        """Verify ExtractionResult can populate GraphStoreService conforming backends."""
        text = """# Service Architecture
Identity Service (svc-identity) is owned by Identity Team (team-identity).
Identity Service depends on Redis Cluster.
Customer Acme Corp uses Identity Service.
"""
        extractor = EntityRelationshipExtractor()
        result = extractor.extract_from_text(text, doc_id="arch-doc")

        graph_store = InMemoryGraphStore()
        result.index_into_graph_store(graph_store)

        assert graph_store.node_count() >= 2
        assert graph_store.edge_count() >= 1

        # Check neighbor traversal
        team_neighbors = graph_store.get_neighbors("team-identity")
        assert len(team_neighbors) >= 1

    def test_extraction_from_document_chunks(self) -> None:
        """Verify extraction across chunked documents with locators and hierarchy."""
        parser = DocumentParser()
        chunker = SemanticChunker(chunk_size=300, chunk_overlap=50)

        postmortem_path = Path(
            "sample_data/documents/postmortem-inc-2031-payments-api-outage.md"
        )
        parsed_doc = parser.parse_file(postmortem_path)
        chunks = chunker.chunk_document(
            parsed_doc.text, doc_id=parsed_doc.id, metadata=parsed_doc.metadata
        )

        extractor = EntityRelationshipExtractor()
        result = extractor.extract_from_chunks(chunks)

        assert len(result.entities) >= 5
        assert len(result.relationships) >= 4

        # Locators must be carried forward
        locators = {e.source_locator for e in result.entities if e.source_locator}
        assert len(locators) >= 1
        assert any("chunk" in loc for loc in locators)


class TestSampleDataKnowledgeGraphCorpus:
    """Integration test building knowledge graph from the 15 sample documents."""

    def test_build_knowledge_graph_from_sample_documents(self) -> None:
        """Verify entity and relationship extraction across all 15 sample documents."""
        docs_dir = Path("sample_data/documents")
        assert docs_dir.exists()

        parser = DocumentParser()
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=64)
        extractor = EntityRelationshipExtractor()
        graph_store = InMemoryGraphStore()

        doc_files = sorted(docs_dir.glob("*.md"))
        total_entities = 0
        total_relationships = 0

        for file_path in doc_files:
            parsed_doc = parser.parse_file(file_path)
            chunks = chunker.chunk_document(
                parsed_doc.text, doc_id=parsed_doc.id, metadata=parsed_doc.metadata
            )
            result = extractor.extract_from_chunks(chunks)

            total_entities += len(result.entities)
            total_relationships += len(result.relationships)
            result.index_into_graph_store(graph_store)

        assert total_entities > 20
        assert total_relationships > 15
        assert graph_store.node_count() >= 10
        assert graph_store.edge_count() >= 8

        # Verify key entities are present in knowledge graph
        assert graph_store.get_node("svc-payments-api") is not None
        assert graph_store.get_node("team-payments") is not None
        assert graph_store.get_node("inc-2031") is not None
        assert graph_store.get_node("cust-acme") is not None

        # Verify customer impact traversal works
        impacted = graph_store.execute_traversal(
            "customer_impact", {"customer_id": "cust-acme"}
        )
        assert len(impacted) >= 1
