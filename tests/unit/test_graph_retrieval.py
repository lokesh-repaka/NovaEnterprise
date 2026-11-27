"""Unit and integration tests for Governed Graph Retrieval and Typed Traversals (P6-3, F8, F14).

Validates:
- Structured Cypher query templates (blast radius, customer impact, team ownership, etc.)
- Graph seeding from sample_data JSON files
- Execution of typed traversals returning canonical Evidence models
- Exposure of executed Cypher string and graph locators
- Rejection of write queries with CypherValidationError
- GraphRetriever class interface
"""

from collections.abc import Generator
from pathlib import Path

import pytest

from backend.app.schemas.common import Evidence
from rag.graph_retrieval import (
    CypherValidationError,
    GraphQueryTemplate,
    GraphRetriever,
    execute_governed_traversal,
    execute_read_only_cypher,
    get_customer_impact_template,
    get_decision_lineage_template,
    get_incident_blast_radius_template,
    get_service_dependencies_template,
    get_service_incidents_template,
    get_team_ownership_template,
    seed_graph_from_domain,
)
from rag.graph_store import InMemoryGraphStore


@pytest.fixture
def graph_store() -> Generator[InMemoryGraphStore, None, None]:
    """Initialize an InMemoryGraphStore populated with domain sample data."""
    store = InMemoryGraphStore()
    sample_dir = Path(__file__).resolve().parents[2] / "sample_data"
    seed_graph_from_domain(store, sample_data_dir=sample_dir)
    yield store
    store.clear()


def test_graph_query_templates_format() -> None:
    """Verify built-in graph templates format correctly into valid parameterized Cypher."""
    # 1. Incident blast radius
    t1 = get_incident_blast_radius_template(incident_id="inc-2031")
    assert isinstance(t1, GraphQueryTemplate)
    assert t1.traversal_type == "incident_blast_radius"
    assert "Incident" in t1.cypher
    assert "AFFECTED" in t1.cypher
    assert t1.params == {"incident_id": "inc-2031"}

    # 2. Customer impact
    t2 = get_customer_impact_template(customer_id="cust-acme")
    assert t2.traversal_type == "customer_impact"
    assert "Customer" in t2.cypher
    assert "IMPACTED" in t2.cypher
    assert t2.params == {"customer_id": "cust-acme"}

    # 3. Service dependencies
    t3 = get_service_dependencies_template(service_id="svc-payments-api")
    assert t3.traversal_type == "service_dependencies"
    assert "Service" in t3.cypher
    assert t3.params == {"service_id": "svc-payments-api"}

    # 4. Team ownership
    t4 = get_team_ownership_template(team_id="team-payments")
    assert t4.traversal_type == "team_ownership"
    assert "Team" in t4.cypher
    assert t4.params == {"team_id": "team-payments"}

    # 5. Service incidents
    t5 = get_service_incidents_template(service_id="svc-payments-api")
    assert t5.traversal_type == "service_incidents"
    assert "Service" in t5.cypher
    assert t5.params == {"service_id": "svc-payments-api"}

    # 6. Decision lineage
    t6 = get_decision_lineage_template(decision_id="dec-adr-042")
    assert t6.traversal_type == "decision_lineage"
    assert "Decision" in t6.cypher
    assert t6.params == {"decision_id": "dec-adr-042"}


def test_seed_graph_from_domain(graph_store: InMemoryGraphStore) -> None:
    """Verify seed_graph_from_domain loads domain entities and edges from sample data."""
    # Should have loaded nodes for teams, employees, services, customers, incidents, decisions, projects, tickets
    assert graph_store.node_count() >= 50
    assert graph_store.edge_count() >= 40

    # Key entity nodes must exist
    inc = graph_store.get_node("inc-2031")
    assert inc is not None
    assert inc["label"] == "Incident"

    svc = graph_store.get_node("svc-payments-api")
    assert svc is not None
    assert svc["label"] == "Service"

    cust = graph_store.get_node("cust-acme")
    assert cust is not None
    assert cust["label"] == "Customer"

    team = graph_store.get_node("team-payments")
    assert team is not None
    assert team["label"] == "Team"

    adr = graph_store.get_node("dec-adr-042")
    assert adr is not None
    assert adr["label"] == "Decision"


def test_execute_governed_traversal_incident_blast_radius(
    graph_store: InMemoryGraphStore,
) -> None:
    """Verify incident_blast_radius traversal produces canonical graph Evidence items with locators and Cypher."""
    evidence_items = execute_governed_traversal(
        traversal_type="incident_blast_radius",
        params={"incident_id": "inc-2031"},
        graph_store=graph_store,
        sub_question_id="sq_graph_1",
    )

    assert isinstance(evidence_items, list)
    assert len(evidence_items) > 0

    # Check evidence structure
    for item in evidence_items:
        assert isinstance(item, Evidence)
        assert item.source_type == "graph"
        assert item.sub_question_id == "sq_graph_1"
        assert item.score == 1.0
        assert item.metadata["store"] == "graph"
        assert item.metadata["traversal_type"] == "incident_blast_radius"
        assert "cypher" in item.metadata
        assert "MATCH" in item.metadata["cypher"]
        # Locator must start with ( and end with )
        assert item.locator.startswith("(")
        assert item.locator.endswith(")")

    # Must contain affected service edge: (Incident:inc-2031)-[:AFFECTED]->(Service:svc-payments-api)
    locators = [e.locator for e in evidence_items]
    assert any("AFFECTED" in loc and "svc-payments-api" in loc for loc in locators)
    # Must contain impacted customer edge: (Incident:inc-2031)-[:IMPACTED]->(Customer:cust-acme)
    assert any("IMPACTED" in loc and "cust-acme" in loc for loc in locators)


def test_execute_governed_traversal_customer_impact(
    graph_store: InMemoryGraphStore,
) -> None:
    """Verify customer_impact traversal returns incidents and services affecting a customer."""
    evidence_items = execute_governed_traversal(
        traversal_type="customer_impact",
        params={"customer_id": "cust-acme"},
        graph_store=graph_store,
        sub_question_id="sq_graph_2",
    )

    assert len(evidence_items) > 0
    assert all(e.source_type == "graph" for e in evidence_items)
    locators = [e.locator for e in evidence_items]
    assert any("cust-acme" in loc for loc in locators)


def test_execute_governed_traversal_team_ownership(
    graph_store: InMemoryGraphStore,
) -> None:
    """Verify team_ownership traversal returns services owned by the team."""
    evidence_items = execute_governed_traversal(
        traversal_type="team_ownership",
        params={"team_id": "team-payments"},
        graph_store=graph_store,
        sub_question_id="sq_graph_3",
    )

    assert len(evidence_items) > 0
    locators = [e.locator for e in evidence_items]
    assert any("team-payments" in loc and "svc-payments-api" in loc for loc in locators)


def test_execute_read_only_cypher_returns_evidence(
    graph_store: InMemoryGraphStore,
) -> None:
    """Verify execute_read_only_cypher executes valid queries and rejects writes."""
    cypher = "MATCH (s:Service) RETURN s"
    evidence_items = execute_read_only_cypher(
        cypher=cypher,
        graph_store=graph_store,
        sub_question_id="sq_graph_4",
    )
    assert len(evidence_items) > 0
    assert all(e.source_type == "graph" for e in evidence_items)

    # Rejection of write operations
    with pytest.raises(CypherValidationError):
        execute_read_only_cypher(
            cypher="CREATE (n:Service {name: 'Exploit'})",
            graph_store=graph_store,
        )

    with pytest.raises(CypherValidationError):
        execute_read_only_cypher(
            cypher="MATCH (n) DETACH DELETE n",
            graph_store=graph_store,
        )


def test_graph_retriever_class_interface(
    graph_store: InMemoryGraphStore,
) -> None:
    """Verify GraphRetriever class wraps traversals, queries, and templates."""
    retriever = GraphRetriever(graph_store=graph_store)

    # 1. Traversal by name
    res1 = retriever.retrieve_traversal(
        traversal_type="incident_blast_radius",
        params={"incident_id": "inc-2031"},
        sub_question_id="sq_r1",
    )
    assert len(res1) > 0
    assert all(e.source_type == "graph" for e in res1)

    # 2. Traversal from template
    tmpl = get_decision_lineage_template(decision_id="dec-adr-042")
    res2 = retriever.retrieve_from_template(tmpl, sub_question_id="sq_r2")
    assert len(res2) > 0
    assert any("adr-042" in e.locator for e in res2)

    # 3. Direct read-only query
    res3 = retriever.retrieve(
        query="MATCH (n:Customer) RETURN n",
        sub_question_id="sq_r3",
    )
    assert len(res3) > 0
    assert all(e.source_type == "graph" for e in res3)
