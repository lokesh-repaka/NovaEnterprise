"""Entity and relationship extraction for NovaEnterprise knowledge graph (P5-3, F13).

Extracts enterprise entities (Service, Incident, Customer, Team, ADR, Employee)
and typed relationships (AFFECTED, IMPACTED, OWNS, ADDRESSED_BY, DEPENDS_ON)
from technical documents and semantic chunks.
"""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from rag.graph_store import GraphEdge, GraphNode

if TYPE_CHECKING:
    from rag.chunker import ParsedChunk
    from rag.graph_store import GraphStoreService
    from rag.parser import ParsedDocument


class ExtractedEntity(BaseModel):
    """Recognized domain entity with classification and source attribution."""

    id: str = Field(..., description="Canonical entity identifier (e.g. svc-payments-api)")
    label: str = Field(..., description="Entity classification (Service, Incident, Customer, Team, ADR, Employee)")
    name: str = Field(..., description="Human-readable entity name or title")
    properties: dict[str, Any] = Field(default_factory=dict, description="Extracted entity properties")
    source_locator: str | None = Field(default=None, description="Citation locator of chunk where identified")
    confidence: float = Field(default=1.0, description="Extraction confidence score (0.0 to 1.0)")

    def to_graph_node(self) -> GraphNode:
        """Convert extracted entity to GraphNode model for GraphStoreService."""
        props = dict(self.properties)
        props["name"] = self.name
        if self.source_locator:
            props["source_locator"] = self.source_locator
        return GraphNode(
            id=self.id,
            label=self.label,
            properties=props,
        )


class ExtractedRelationship(BaseModel):
    """Directed typed relationship connecting two extracted domain entities."""

    source_id: str = Field(..., description="Source node canonical ID")
    target_id: str = Field(..., description="Target node canonical ID")
    type: str = Field(..., description="Relationship verb (AFFECTED, IMPACTED, OWNS, ADDRESSED_BY, DEPENDS_ON)")
    properties: dict[str, Any] = Field(default_factory=dict, description="Relationship metadata")
    source_locator: str | None = Field(default=None, description="Citation locator")
    confidence: float = Field(default=1.0, description="Extraction confidence score")

    def to_graph_edge(self) -> GraphEdge:
        """Convert extracted relationship to GraphEdge model for GraphStoreService."""
        props = dict(self.properties)
        if self.source_locator:
            props["source_locator"] = self.source_locator
        return GraphEdge(
            source=self.source_id,
            target=self.target_id,
            type=self.type,
            properties=props,
        )


class ExtractionResult(BaseModel):
    """Consolidated entity and relationship extraction payload."""

    entities: list[ExtractedEntity] = Field(default_factory=list, description="Extracted domain entities")
    relationships: list[ExtractedRelationship] = Field(
        default_factory=list, description="Extracted domain relationships"
    )
    doc_id: str | None = Field(default=None, description="Originating document identifier")

    def index_into_graph_store(self, graph_store: GraphStoreService) -> None:
        """Populate extracted nodes and edges into any GraphStoreService conforming backend."""
        for entity in self.entities:
            node = entity.to_graph_node()
            graph_store.add_node(node.id, node.label, node.properties)

        for rel in self.relationships:
            edge = rel.to_graph_edge()
            graph_store.add_edge(edge.source, edge.target, edge.type, edge.properties)


class EntityRelationshipExtractor:
    """Deterministic, offline rule-based entity and relationship extractor (N1, F13).

    Recognizes canonical enterprise entities and builds multi-hop graph edges
    from document metadata and section content.
    """

    def __init__(self, sample_data_dir: Path | str | None = None) -> None:
        """Initialize extractor with canonical domain entity dictionaries."""
        self.sample_data_dir = Path(sample_data_dir) if sample_data_dir else Path("sample_data")
        self._services: dict[str, str] = {}
        self._teams: dict[str, str] = {}
        self._customers: dict[str, str] = {}
        self._incidents: dict[str, str] = {}
        self._decisions: dict[str, str] = {}
        self._load_domain_vocabularies()

    def _load_domain_vocabularies(self) -> None:
        """Load known entity IDs and names from sample_data/ or initialize built-in standards."""
        # Built-in fallbacks matching Claude.md §6
        services_map = {
            "payments api": "svc-payments-api",
            "svc-payments-api": "svc-payments-api",
            "identity service": "svc-identity",
            "svc-identity": "svc-identity",
            "data pipeline": "svc-data-pipeline",
            "svc-data-pipeline": "svc-data-pipeline",
            "analytics dashboard": "svc-analytics-dashboard",
            "svc-analytics-dashboard": "svc-analytics-dashboard",
            "notification service": "svc-notifications",
            "svc-notifications": "svc-notifications",
            "billing engine": "svc-billing-engine",
            "svc-billing-engine": "svc-billing-engine",
            "customer portal": "svc-customer-portal",
            "svc-customer-portal": "svc-customer-portal",
            "search service": "svc-search",
            "svc-search": "svc-search",
        }
        teams_map = {
            "payments platform": "team-payments",
            "team-payments": "team-payments",
            "identity team": "team-identity",
            "identity": "team-identity",
            "team-identity": "team-identity",
            "data platform": "team-data",
            "team-data": "team-data",
            "customer success": "team-customer-success",
            "team-customer-success": "team-customer-success",
            "sre": "team-sre",
            "team-sre": "team-sre",
            "analytics platform": "team-analytics",
            "analytics": "team-analytics",
            "team-analytics": "team-analytics",
        }
        customers_map = {
            "acme corp": "cust-acme",
            "cust-acme": "cust-acme",
            "globex corp": "cust-globex",
            "cust-globex": "cust-globex",
            "wayne enterprises": "cust-wayne",
            "cust-wayne": "cust-wayne",
            "initech": "cust-initech",
            "cust-initech": "cust-initech",
            "umbrella corp": "cust-umbrella",
            "cust-umbrella": "cust-umbrella",
            "stark industries": "cust-stark",
            "cust-stark": "cust-stark",
            "cyberdyne systems": "cust-cyberdyne",
            "cust-cyberdyne": "cust-cyberdyne",
            "hooli": "cust-hooli",
            "cust-hooli": "cust-hooli",
            "massive dynamic": "cust-massive-dynamic",
            "cust-massive-dynamic": "cust-massive-dynamic",
            "soylent corp": "cust-soylent",
            "cust-soylent": "cust-soylent",
        }

        # Load from disk if available
        if self.sample_data_dir.exists():
            svc_file = self.sample_data_dir / "services.json"
            if svc_file.exists():
                with contextlib.suppress(Exception):
                    for item in json.loads(svc_file.read_text(encoding="utf-8")):
                        services_map[item["name"].lower()] = item["id"]
                        services_map[item["id"].lower()] = item["id"]

            team_file = self.sample_data_dir / "teams.json"
            if team_file.exists():
                with contextlib.suppress(Exception):
                    for item in json.loads(team_file.read_text(encoding="utf-8")):
                        teams_map[item["name"].lower()] = item["id"]
                        teams_map[item["id"].lower()] = item["id"]

            cust_file = self.sample_data_dir / "customers.json"
            if cust_file.exists():
                with contextlib.suppress(Exception):
                    for item in json.loads(cust_file.read_text(encoding="utf-8")):
                        customers_map[item["name"].lower()] = item["id"]
                        customers_map[item["id"].lower()] = item["id"]

        self._services = services_map
        self._teams = teams_map
        self._customers = customers_map

    def _match_service(self, text: str) -> str | None:
        """Find matching service ID in text string."""
        text_lower = text.lower()
        for k, v in self._services.items():
            if k in text_lower:
                return v
        return None

    def _match_team(self, text: str) -> str | None:
        """Find matching team ID in text string."""
        text_lower = text.lower()
        for k, v in self._teams.items():
            if k in text_lower:
                return v
        return None

    def _canonicalize_incident(self, match_str: str) -> str:
        """Convert INC-2031 or inc-2031 to canonical inc-2031 format."""
        digits = re.search(r"\d+", match_str)
        if digits:
            return f"inc-{digits.group(0)}"
        return match_str.lower()

    def _canonicalize_decision(self, match_str: str) -> str:
        """Convert ADR-042 or dec-adr-042 to canonical dec-adr-042 format."""
        digits = re.search(r"\d+", match_str)
        if digits:
            return f"dec-adr-{digits.group(0)}"
        return match_str.lower()

    def extract_from_text(
        self,
        text: str,
        doc_id: str | None = None,
        locator: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Extract domain entities and relationships from raw text."""
        doc_meta = metadata or {}
        entities_by_id: dict[str, ExtractedEntity] = {}
        relationships: list[ExtractedRelationship] = []

        text_lower = text.lower()

        # 1. Extract Incidents
        incident_matches = re.findall(r"\b(?:INC|inc)[-_]?(\d{4})\b", text)
        for num in set(incident_matches):
            inc_id = f"inc-{num}"
            entities_by_id[inc_id] = ExtractedEntity(
                id=inc_id,
                label="Incident",
                name=f"Incident INC-{num}",
                properties={"incident_number": num},
                source_locator=locator,
            )

        # 2. Extract Services
        for name_key, svc_id in self._services.items():
            if svc_id not in entities_by_id and re.search(rf"\b{re.escape(name_key)}\b", text_lower):
                entities_by_id[svc_id] = ExtractedEntity(
                    id=svc_id,
                    label="Service",
                    name=name_key.title() if "svc-" not in name_key else name_key,
                    properties={"service_id": svc_id},
                    source_locator=locator,
                )

        # 3. Extract Teams
        for name_key, team_id in self._teams.items():
            if team_id not in entities_by_id and re.search(rf"\b{re.escape(name_key)}\b", text_lower):
                entities_by_id[team_id] = ExtractedEntity(
                    id=team_id,
                    label="Team",
                    name=name_key.title() if "team-" not in name_key else name_key,
                    properties={"team_id": team_id},
                    source_locator=locator,
                )

        # 4. Extract Customers
        for name_key, cust_id in self._customers.items():
            if cust_id not in entities_by_id and re.search(rf"\b{re.escape(name_key)}\b", text_lower):
                entities_by_id[cust_id] = ExtractedEntity(
                    id=cust_id,
                    label="Customer",
                    name=name_key.title() if "cust-" not in name_key else name_key,
                    properties={"customer_id": cust_id},
                    source_locator=locator,
                )

        # 5. Extract ADRs / Decisions
        adr_matches = re.findall(r"\b(?:ADR|adr)[-_]?(\d{3})\b", text)
        for num in set(adr_matches):
            dec_id = f"dec-adr-{num}"
            entities_by_id[dec_id] = ExtractedEntity(
                id=dec_id,
                label="ADR",
                name=f"ADR-{num}",
                properties={"adr_number": num},
                source_locator=locator,
            )

        # 6. Extract Employees (from investigator/author attributes)
        emp_match = re.search(
            r"(?:lead investigator|author|sign-off|engineer):\s*([A-Za-z]+ [A-Za-z]+)",
            text,
            re.IGNORECASE,
        )
        if emp_match:
            emp_name = emp_match.group(1).strip()
            emp_id = f"emp-{emp_name.lower().replace(' ', '-')}"
            entities_by_id[emp_id] = ExtractedEntity(
                id=emp_id,
                label="Employee",
                name=emp_name,
                properties={"full_name": emp_name},
                source_locator=locator,
            )

        # Extract Relationships
        incidents = [e for e in entities_by_id.values() if e.label == "Incident"]
        services = [e for e in entities_by_id.values() if e.label == "Service"]
        teams = [e for e in entities_by_id.values() if e.label == "Team"]
        customers = [e for e in entities_by_id.values() if e.label == "Customer"]
        adrs = [e for e in entities_by_id.values() if e.label == "ADR"]

        # Link from document metadata if available
        meta_target_svc = doc_meta.get("target_service") or doc_meta.get("service")
        matched_svc = self._match_service(str(meta_target_svc)) if meta_target_svc else None
        if matched_svc:
            for inc in incidents:
                relationships.append(
                    ExtractedRelationship(
                        source_id=inc.id,
                        target_id=matched_svc,
                        type="AFFECTED",
                        properties={"source": "document_metadata"},
                        source_locator=locator,
                    )
                )

        meta_team = doc_meta.get("owning_team") or doc_meta.get("team")
        matched_team = self._match_team(str(meta_team)) if meta_team else None
        if matched_team:
            for svc in services:
                relationships.append(
                    ExtractedRelationship(
                        source_id=matched_team,
                        target_id=svc.id,
                        type="OWNS",
                        properties={"source": "document_metadata"},
                        source_locator=locator,
                    )
                )
                relationships.append(
                    ExtractedRelationship(
                        source_id=svc.id,
                        target_id=matched_team,
                        type="OWNED_BY",
                        properties={"source": "document_metadata"},
                        source_locator=locator,
                    )
                )

        # Sentence-level co-occurrence relationship inference
        sentences = re.split(r"[.\n]\s*", text)
        for sent in sentences:
            sent_lower = sent.lower()

            # (Incident)-[:AFFECTED]->(Service)
            if any(k in sent_lower for k in ("affect", "outage", "degrade", "latency", "incident")):
                for inc in incidents:
                    if inc.id in sent_lower or re.search(rf"\b{re.escape(inc.name.lower())}\b", sent_lower):
                        for svc in services:
                            relationships.append(
                                ExtractedRelationship(
                                    source_id=inc.id,
                                    target_id=svc.id,
                                    type="AFFECTED",
                                    source_locator=locator,
                                )
                            )

            # (Incident)-[:IMPACTED]->(Customer)
            if any(k in sent_lower for k in ("impact", "disrupt", "failed", "suffer", "customer")):
                for inc in incidents:
                    for cust in customers:
                        relationships.append(
                            ExtractedRelationship(
                                source_id=inc.id,
                                target_id=cust.id,
                                type="IMPACTED",
                                source_locator=locator,
                            )
                        )

            # (Incident)-[:ADDRESSED_BY]->(ADR)
            if any(k in sent_lower for k in ("address", "decision", "adopt", "prevent", "corrective", "adr")):
                for inc in incidents:
                    for adr in adrs:
                        relationships.append(
                            ExtractedRelationship(
                                source_id=inc.id,
                                target_id=adr.id,
                                type="ADDRESSED_BY",
                                source_locator=locator,
                            )
                        )
                        relationships.append(
                            ExtractedRelationship(
                                source_id=adr.id,
                                target_id=inc.id,
                                type="ADDRESSES",
                                source_locator=locator,
                            )
                        )

            # (Team)-[:OWNS]->(Service)
            if any(k in sent_lower for k in ("own", "maintain", "responsible")):
                for team in teams:
                    for svc in services:
                        relationships.append(
                            ExtractedRelationship(
                                source_id=team.id,
                                target_id=svc.id,
                                type="OWNS",
                                source_locator=locator,
                            )
                        )

        # Deduplicate relationships
        unique_rels: list[ExtractedRelationship] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for r in relationships:
            sig = (r.source_id, r.type, r.target_id)
            if sig not in seen_edges and r.source_id != r.target_id:
                seen_edges.add(sig)
                unique_rels.append(r)

        return ExtractionResult(
            entities=list(entities_by_id.values()),
            relationships=unique_rels,
            doc_id=doc_id,
        )

    def extract_from_chunk(self, chunk: ParsedChunk) -> ExtractionResult:
        """Extract entities and relationships from a semantic chunk."""
        return self.extract_from_text(
            text=chunk.text,
            doc_id=chunk.doc_id,
            locator=chunk.locator,
            metadata=chunk.metadata,
        )

    def extract_from_document(self, doc: ParsedDocument) -> ExtractionResult:
        """Extract entities and relationships from a parsed document."""
        return self.extract_from_text(
            text=doc.text,
            doc_id=doc.id,
            locator=f"doc:{doc.id}",
            metadata=doc.metadata,
        )

    def extract_from_chunks(self, chunks: list[ParsedChunk]) -> ExtractionResult:
        """Aggregate and deduplicate extractions across a document's semantic chunks."""
        entities_by_id: dict[str, ExtractedEntity] = {}
        relationships: list[ExtractedRelationship] = []
        seen_edges: set[tuple[str, str, str]] = set()

        doc_id = chunks[0].doc_id if chunks else None

        for chunk in chunks:
            chunk_result = self.extract_from_chunk(chunk)
            for entity in chunk_result.entities:
                if entity.id not in entities_by_id:
                    entities_by_id[entity.id] = entity

            for rel in chunk_result.relationships:
                sig = (rel.source_id, rel.type, rel.target_id)
                if sig not in seen_edges and rel.source_id != rel.target_id:
                    seen_edges.add(sig)
                    relationships.append(rel)

        # Link document-wide entities across chunks for postmortems and architectural documents
        incidents = [e for e in entities_by_id.values() if e.label == "Incident"]
        services = [e for e in entities_by_id.values() if e.label == "Service"]
        teams = [e for e in entities_by_id.values() if e.label == "Team"]
        customers = [e for e in entities_by_id.values() if e.label == "Customer"]
        adrs = [e for e in entities_by_id.values() if e.label == "ADR"]

        doc_locator = f"doc:{doc_id}" if doc_id else None

        for inc in incidents:
            for svc in services:
                sig = (inc.id, "AFFECTED", svc.id)
                if sig not in seen_edges and inc.id != svc.id:
                    seen_edges.add(sig)
                    relationships.append(
                        ExtractedRelationship(
                            source_id=inc.id,
                            target_id=svc.id,
                            type="AFFECTED",
                            source_locator=doc_locator,
                        )
                    )
            for cust in customers:
                sig = (inc.id, "IMPACTED", cust.id)
                if sig not in seen_edges and inc.id != cust.id:
                    seen_edges.add(sig)
                    relationships.append(
                        ExtractedRelationship(
                            source_id=inc.id,
                            target_id=cust.id,
                            type="IMPACTED",
                            source_locator=doc_locator,
                        )
                    )
            for adr in adrs:
                sig1 = (inc.id, "ADDRESSED_BY", adr.id)
                sig2 = (adr.id, "ADDRESSES", inc.id)
                if sig1 not in seen_edges:
                    seen_edges.add(sig1)
                    relationships.append(
                        ExtractedRelationship(
                            source_id=inc.id,
                            target_id=adr.id,
                            type="ADDRESSED_BY",
                            source_locator=doc_locator,
                        )
                    )
                if sig2 not in seen_edges:
                    seen_edges.add(sig2)
                    relationships.append(
                        ExtractedRelationship(
                            source_id=adr.id,
                            target_id=inc.id,
                            type="ADDRESSES",
                            source_locator=doc_locator,
                        )
                    )

        for team in teams:
            for svc in services:
                sig = (team.id, "OWNS", svc.id)
                if sig not in seen_edges and team.id != svc.id:
                    seen_edges.add(sig)
                    relationships.append(
                        ExtractedRelationship(
                            source_id=team.id,
                            target_id=svc.id,
                            type="OWNS",
                            source_locator=doc_locator,
                        )
                    )

        return ExtractionResult(
            entities=list(entities_by_id.values()),
            relationships=relationships,
            doc_id=doc_id,
        )
