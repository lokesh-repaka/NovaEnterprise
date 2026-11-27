"""Unit tests for canonical Evidence schema and locator contracts (P6-1, F5–F8).

Validates:
- Unified Evidence schema conformance across Vector/Hybrid, SQL, and Graph paths (Claude.md §5)
- Score boundary validation (0.0 to 1.0) and source_type constraints
- Citation and SubQuestion schemas
- Document, SQL, and Graph locator builders and parsers
- Deterministic evidence ID generation, deduplication, and score sorting
"""

import pytest
from pydantic import ValidationError

from backend.app.schemas.common import (
    Citation,
    Evidence,
    EvidenceSource,
    SubQuestion,
)
from rag.evidence import (
    build_document_locator,
    build_graph_locator,
    build_sql_locator,
    create_document_evidence,
    create_evidence,
    create_graph_evidence,
    create_sql_evidence,
    deduplicate_evidence,
    filter_evidence_by_score,
    generate_evidence_id,
    parse_document_locator,
    parse_graph_locator,
    parse_locator,
    parse_sql_locator,
    sort_evidence_by_score,
    validate_locator,
)


class TestEvidenceSchema:
    """Tests for the canonical Evidence Pydantic model invariants."""

    def test_evidence_instantiation_and_serialization(self) -> None:
        """Verify valid evidence instantiation and JSON serialization matching API_CONTRACT.md §2."""
        evidence = Evidence(
            id="evi_01J8Z9X2A4M8Q9K3",
            sub_question_id="sq1",
            source_type="graph",
            locator="(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)-[:IMPACTED]->(Customer:Acme Corp)",
            content="Customer Acme Corp (tier: enterprise) was impacted by SEV1 outage INC-2031 on Payments API.",
            score=1.0,
            metadata={
                "store": "neo4j",
                "cypher": "MATCH (s:Service {name: 'Payments API'})<-[:AFFECTED]-(i:Incident)-[:IMPACTED]->(c:Customer) RETURN c.name, i.id",
            },
        )

        assert evidence.id == "evi_01J8Z9X2A4M8Q9K3"
        assert evidence.sub_question_id == "sq1"
        assert evidence.source_type == "graph"
        assert evidence.score == 1.0
        assert "store" in evidence.metadata

        # Dict and JSON representation
        dumped = evidence.model_dump()
        assert dumped["source_type"] == "graph"
        assert dumped["id"] == "evi_01J8Z9X2A4M8Q9K3"

    def test_evidence_source_type_validation(self) -> None:
        """Verify source_type only accepts 'document', 'sql', or 'graph'."""
        # Valid sources
        for valid_source in [
            "document",
            "sql",
            "graph",
            EvidenceSource.DOCUMENT,
            EvidenceSource.SQL,
            EvidenceSource.GRAPH,
        ]:
            evi = Evidence(
                id="evi_valid",
                sub_question_id="sq1",
                source_type=valid_source,  # type: ignore[arg-type]
                locator="doc:sample#chunk-1",
                content="Valid content snippet",
                score=0.85,
            )
            assert evi.source_type in {"document", "sql", "graph"}

        # Invalid source
        with pytest.raises(ValidationError):
            Evidence(
                id="evi_invalid",
                sub_question_id="sq1",
                source_type="external_api",  # type: ignore[arg-type]
                locator="http://example.com",
                content="Invalid source",
                score=0.5,
            )

    def test_evidence_score_boundaries(self) -> None:
        """Verify score is constrained to [0.0, 1.0]."""
        # Valid boundaries
        e0 = Evidence(
            id="evi_0",
            sub_question_id="sq1",
            source_type="document",
            locator="doc:1#chunk-0",
            content="test",
            score=0.0,
        )
        assert e0.score == 0.0

        e1 = Evidence(
            id="evi_1",
            sub_question_id="sq1",
            source_type="document",
            locator="doc:1#chunk-0",
            content="test",
            score=1.0,
        )
        assert e1.score == 1.0

        # Score > 1.0 raises ValidationError
        with pytest.raises(ValidationError):
            Evidence(
                id="evi_err",
                sub_question_id="sq1",
                source_type="document",
                locator="doc:1#chunk-0",
                content="test",
                score=1.05,
            )

        # Score < 0.0 raises ValidationError
        with pytest.raises(ValidationError):
            Evidence(
                id="evi_err2",
                sub_question_id="sq1",
                source_type="document",
                locator="doc:1#chunk-0",
                content="test",
                score=-0.1,
            )


class TestCitationAndSubQuestionSchemas:
    """Tests for Citation and SubQuestion schemas."""

    def test_citation_model(self) -> None:
        """Verify Citation model links citation_id to evidence_id with snippet."""
        cit = Citation(
            citation_id=1,
            evidence_id="evi_01J8Z9X2A4M8Q9K3",
            source_type="graph",
            locator="(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)",
            snippet="Customer Acme Corp was impacted by SEV1 outage INC-2031.",
        )
        assert cit.citation_id == 1
        assert cit.evidence_id == "evi_01J8Z9X2A4M8Q9K3"
        assert cit.source_type == "graph"

    def test_sub_question_model(self) -> None:
        """Verify SubQuestion decomposition schema."""
        sq = SubQuestion(
            id="sq1",
            question="What was the root cause of the Payments API outage?",
            strategy="vector",
            status="pending",
        )
        assert sq.id == "sq1"
        assert sq.strategy == "vector"
        assert sq.status == "pending"


class TestLocatorBuildersAndParsers:
    """Tests for Document, SQL, and Graph locator builders and parsers."""

    def test_document_locator_builder_and_parser(self) -> None:
        """Verify document locator formatting and parsing."""
        loc1 = build_document_locator(
            "adr-012-async-payment-callbacks.md", section="Section-2"
        )
        assert loc1 == "documents/adr-012-async-payment-callbacks.md#Section-2"

        parsed1 = parse_document_locator(loc1)
        assert parsed1["filename"] == "adr-012-async-payment-callbacks.md"
        assert parsed1["section"] == "Section-2"
        assert parsed1["chunk_index"] is None

        loc2 = build_document_locator("doc-uuid-1234", chunk_index=3)
        assert loc2 == "doc:doc-uuid-1234#chunk-3"

        parsed2 = parse_document_locator(loc2)
        assert parsed2["doc_id"] == "doc-uuid-1234"
        assert parsed2["chunk_index"] == 3

    def test_sql_locator_builder_and_parser(self) -> None:
        """Verify SQL table and primary key locator formatting and parsing."""
        loc = build_sql_locator("customers", row_id="cust-acme")
        assert loc == "sql:customers:cust-acme"

        parsed = parse_sql_locator(loc)
        assert parsed["table"] == "customers"
        assert parsed["row_id"] == "cust-acme"

        loc_table_only = build_sql_locator("incidents")
        assert loc_table_only == "sql:incidents"
        assert parse_sql_locator(loc_table_only)["table"] == "incidents"

    def test_graph_locator_builder_and_parser(self) -> None:
        """Verify Graph traversal locator formatting and parsing."""
        loc = build_graph_locator(
            source_label="Service",
            source_id="svc-payments-api",
            rel_type="AFFECTED",
            target_label="Incident",
            target_id="inc-2031",
            direction="in",
        )
        assert loc == "(Service:svc-payments-api)<-[:AFFECTED]-(Incident:inc-2031)"

        parsed = parse_graph_locator(loc)
        assert parsed["source_label"] == "Service"
        assert parsed["source_id"] == "svc-payments-api"
        assert parsed["rel_type"] == "AFFECTED"
        assert parsed["target_label"] == "Incident"
        assert parsed["target_id"] == "inc-2031"

    def test_generic_locator_validation_and_parsing(self) -> None:
        """Verify parse_locator dynamically detects source type and validates format."""
        doc_loc = "documents/policy-data-retention.md#Retention-Schedules"
        sql_loc = "sql:services:svc-payments-api"
        graph_loc = "(Incident:inc-2031)-[:IMPACTED]->(Customer:cust-acme)"

        assert validate_locator(doc_loc, expected_type="document") is True
        assert validate_locator(sql_loc, expected_type="sql") is True
        assert validate_locator(graph_loc, expected_type="graph") is True

        # Type mismatch validation
        assert validate_locator(doc_loc, expected_type="sql") is False

        p_doc = parse_locator(doc_loc)
        assert p_doc["source_type"] == "document"

        p_sql = parse_locator(sql_loc)
        assert p_sql["source_type"] == "sql"

        p_graph = parse_locator(graph_loc)
        assert p_graph["source_type"] == "graph"


class TestEvidenceUtilities:
    """Tests for evidence factories, ID generation, deduplication, and ranking."""

    def test_deterministic_evidence_id_generation(self) -> None:
        """Verify deterministic evidence IDs are prefixed with 'evi_' and reproducible."""
        id1 = generate_evidence_id(
            sub_question_id="sq1",
            source_type="sql",
            locator="sql:customers:cust-acme",
            content="Customer Acme contract value: $2,400,000",
        )
        id2 = generate_evidence_id(
            sub_question_id="sq1",
            source_type="sql",
            locator="sql:customers:cust-acme",
            content="Customer Acme contract value: $2,400,000",
        )
        assert id1.startswith("evi_")
        assert id1 == id2

    def test_typed_evidence_creators(self) -> None:
        """Verify convenience evidence creators for document, SQL, and graph."""
        doc_evi = create_document_evidence(
            sub_question_id="sq1",
            doc_id_or_filename="postmortem-inc-2031.md",
            content="Database connection pool exhaustion caused degradation.",
            section="Executive Summary",
            score=0.92,
        )
        assert doc_evi.source_type == "document"
        assert "postmortem-inc-2031.md#Executive Summary" in doc_evi.locator
        assert doc_evi.score == 0.92

        sql_evi = create_sql_evidence(
            sub_question_id="sq2",
            table="incidents",
            row_id="inc-2031",
            content="severity=SEV1, status=resolved",
            query="SELECT * FROM incidents WHERE id = 'inc-2031'",
            score=1.0,
        )
        assert sql_evi.source_type == "sql"
        assert sql_evi.locator == "sql:incidents:inc-2031"
        assert sql_evi.metadata.get("sql_query") is not None

        graph_evi = create_graph_evidence(
            sub_question_id="sq3",
            locator="(Service:Payments API)<-[:AFFECTED]-(Incident:INC-2031)",
            content="Payments API affected by INC-2031",
            cypher="MATCH (s:Service)<-[:AFFECTED]-(i:Incident) RETURN s, i",
            score=0.98,
        )
        assert graph_evi.source_type == "graph"
        assert graph_evi.metadata.get("cypher") is not None

    def test_deduplicate_and_sort_evidence(self) -> None:
        """Verify evidence deduplication retains highest score and sorting operates descending."""
        e1 = create_evidence(
            sub_question_id="sq1",
            source_type="document",
            locator="doc:1#chunk-0",
            content="duplicate content",
            score=0.6,
        )
        e2 = create_evidence(
            sub_question_id="sq2",
            source_type="document",
            locator="doc:1#chunk-0",
            content="duplicate content higher score",
            score=0.9,
        )
        e3 = create_evidence(
            sub_question_id="sq1",
            source_type="sql",
            locator="sql:customers:cust-acme",
            content="Customer Acme",
            score=0.8,
        )

        deduped = deduplicate_evidence([e1, e2, e3])
        assert len(deduped) == 2
        # Check that the higher scored duplicate (0.9) was preserved
        doc_item = next(e for e in deduped if e.source_type == "document")
        assert doc_item.score == 0.9

        # Test sorting
        sorted_items = sort_evidence_by_score(deduped, descending=True)
        assert sorted_items[0].score == 0.9
        assert sorted_items[1].score == 0.8

        # Test score filtering
        filtered = filter_evidence_by_score(deduped, min_score=0.85)
        assert len(filtered) == 1
        assert filtered[0].score == 0.9
