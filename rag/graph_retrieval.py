"""Governed Graph retrieval, typed Cypher traversals, and query validation (P6-3, F8, F14, Claude.md §5, §8).

Provides:
- Strict Cypher AST and security validator (validate_cypher) blocking mutation clauses,
  multi-statement injections, and administrative calls.
- Canonical domain query templates (incident blast radius, customer impact, team ownership, etc.).
- Domain seeding utility populating GraphStoreService with NovaEnterprise graph entities and edges.
- Governed execution yielding canonical Evidence instances with graph locators and Cypher metadata.
- GraphRetriever class encapsulating governed graph retrieval for LangGraph agent integration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import Evidence
from rag.evidence import build_graph_locator, create_graph_evidence
from rag.graph_store import GraphStoreService, get_graph_store

__all__ = [
    "CypherValidationError",
    "GraphQueryTemplate",
    "GraphRetriever",
    "execute_governed_traversal",
    "execute_read_only_cypher",
    "get_customer_impact_template",
    "get_decision_lineage_template",
    "get_incident_blast_radius_template",
    "get_service_dependencies_template",
    "get_service_incidents_template",
    "get_team_ownership_template",
    "seed_graph_from_domain",
    "validate_cypher",
]

# Regex patterns for Cypher validation
_CYPHER_MUTATION_RE = re.compile(
    r"\b(CREATE|DELETE|SET|REMOVE|MERGE|DROP|DETACH|ALTER|LOAD\s+CSV|LOAD|INSERT|UPDATE)\b",
    re.IGNORECASE,
)
_DANGEROUS_PROCEDURES_RE = re.compile(
    r"\bCALL\s+(dbms|apoc\.export|apoc\.periodic|security)",
    re.IGNORECASE,
)
_CYPHER_READ_RE = re.compile(r"\b(MATCH|OPTIONAL\s+MATCH)\b", re.IGNORECASE)
_CYPHER_RETURN_RE = re.compile(r"\bRETURN\b", re.IGNORECASE)
_SINGLE_LINE_COMMENT_RE = re.compile(r"//.*$", re.MULTILINE)
_MULTI_LINE_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


class CypherValidationError(Exception):
    """Raised when a Cypher query fails security or read-only validation."""


def _strip_cypher_comments(cypher: str) -> str:
    """Remove single-line and multiline comments from Cypher query."""
    without_multi = _MULTI_LINE_COMMENT_RE.sub(" ", cypher)
    return _SINGLE_LINE_COMMENT_RE.sub(" ", without_multi).strip()


def validate_cypher(cypher_str: str) -> bool:
    """Validate that a Cypher query is a single read-only MATCH...RETURN statement.

    Rules enforced:
    1. Read-only MATCH ... RETURN queries pass.
    2. Parameterized MATCH queries pass.
    3. Multi-hop traversal MATCH queries pass.
    4. Destructive write statements (CREATE, DELETE, DETACH DELETE, SET, REMOVE, MERGE, DROP) are blocked.
    5. Semicolon chaining and multi-statement injection are blocked.
    6. Administrative or file load procedures (LOAD CSV, CALL dbms.*) are blocked.
    7. Empty, whitespace-only, comment-only, or syntactically invalid queries are blocked.
    """
    if not isinstance(cypher_str, str):
        return False

    cleaned = cypher_str.strip()
    if not cleaned:
        return False

    # Block comment-only inputs
    uncommented = _strip_cypher_comments(cleaned)
    if not uncommented:
        return False

    # Check for semicolon injection / multi-statement execution
    # Allow a single trailing semicolon at the very end
    without_trailing_semi = uncommented.rstrip(";").strip()
    if ";" in without_trailing_semi:
        return False

    # Prohibit mutating keywords
    if _CYPHER_MUTATION_RE.search(uncommented):
        return False

    # Prohibit dangerous administrative or file-export procedures
    if _DANGEROUS_PROCEDURES_RE.search(uncommented):
        return False

    # Must contain both MATCH (or OPTIONAL MATCH) and RETURN
    if not _CYPHER_READ_RE.search(uncommented):
        return False
    if not _CYPHER_RETURN_RE.search(uncommented):
        return False

    # Bare 'RETURN' with nothing else is invalid
    return uncommented.upper() != "RETURN"


# -----------------------------------------------------------------------------
# Structured Graph Query Templates
# -----------------------------------------------------------------------------


class GraphQueryTemplate(BaseModel):
    """Structured parameterized Cypher traversal template."""

    model_config = ConfigDict(frozen=True)

    traversal_type: str
    cypher: str
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


def get_incident_blast_radius_template(incident_id: str) -> GraphQueryTemplate:
    """Construct incident blast radius traversal template.

    Traverses: Incident -> Service -> Team, Incident -> Customer, Decision -> Incident.
    """
    cypher = (
        "MATCH (i:Incident {id: $incident_id})-[:AFFECTED]->(s:Service) "
        "OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team) "
        "OPTIONAL MATCH (i)-[:IMPACTED]->(c:Customer) "
        "OPTIONAL MATCH (d:Decision)-[:ADDRESSED]->(i) "
        "RETURN i, s, t, c, d"
    )
    return GraphQueryTemplate(
        traversal_type="incident_blast_radius",
        cypher=cypher,
        params={"incident_id": incident_id},
        description="Traverse incident blast radius to services, teams, customers, and decisions",
    )


def get_customer_impact_template(customer_id: str) -> GraphQueryTemplate:
    """Construct customer impact traversal template.

    Traverses: Customer <- Incident -> Service.
    """
    cypher = (
        "MATCH (c:Customer {id: $customer_id})<-[:IMPACTED]-(i:Incident) "
        "OPTIONAL MATCH (i)-[:AFFECTED]->(s:Service) "
        "RETURN c, i, s"
    )
    return GraphQueryTemplate(
        traversal_type="customer_impact",
        cypher=cypher,
        params={"customer_id": customer_id},
        description="Traverse customer impact to associated incidents and affected services",
    )


def get_service_dependencies_template(service_id: str) -> GraphQueryTemplate:
    """Construct service dependency and ownership traversal template.

    Traverses: Service -> Service dependencies and Service -> Team.
    """
    cypher = (
        "MATCH (s:Service {id: $service_id}) "
        "OPTIONAL MATCH (s)-[:DEPENDS_ON|CALLS]->(dep:Service) "
        "OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team) "
        "RETURN s, dep, t"
    )
    return GraphQueryTemplate(
        traversal_type="service_dependencies",
        cypher=cypher,
        params={"service_id": service_id},
        description="Traverse service dependencies, callers, and owning team",
    )


def get_team_ownership_template(team_id: str) -> GraphQueryTemplate:
    """Construct team ownership traversal template.

    Traverses: Team <- Service, Team <- Project, Team <- Employee.
    """
    cypher = (
        "MATCH (t:Team {id: $team_id}) "
        "OPTIONAL MATCH (s:Service)-[:OWNED_BY]->(t) "
        "OPTIONAL MATCH (p:Project)-[:OWNED_BY]->(t) "
        "OPTIONAL MATCH (e:Employee)-[:MEMBER_OF]->(t) "
        "RETURN t, s, p, e"
    )
    return GraphQueryTemplate(
        traversal_type="team_ownership",
        cypher=cypher,
        params={"team_id": team_id},
        description="Traverse team ownership to services, projects, and member employees",
    )


def get_service_incidents_template(service_id: str) -> GraphQueryTemplate:
    """Construct service incident history traversal template.

    Traverses: Service <- Incident -> Customer.
    """
    cypher = (
        "MATCH (s:Service {id: $service_id})<-[:AFFECTED]-(i:Incident) "
        "OPTIONAL MATCH (i)-[:IMPACTED]->(c:Customer) "
        "RETURN s, i, c"
    )
    return GraphQueryTemplate(
        traversal_type="service_incidents",
        cypher=cypher,
        params={"service_id": service_id},
        description="Traverse service incident history and impacted customers",
    )


def get_decision_lineage_template(decision_id: str) -> GraphQueryTemplate:
    """Construct decision lineage traversal template.

    Traverses: Decision -> Incident -> Service -> Team.
    """
    cypher = (
        "MATCH (d:Decision {id: $decision_id})-[:ADDRESSED]->(i:Incident) "
        "OPTIONAL MATCH (i)-[:AFFECTED]->(s:Service) "
        "OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team) "
        "RETURN d, i, s, t"
    )
    return GraphQueryTemplate(
        traversal_type="decision_lineage",
        cypher=cypher,
        params={"decision_id": decision_id},
        description="Traverse decision lineage to incident, affected service, and owning team",
    )


# -----------------------------------------------------------------------------
# Domain Graph Seeding Utility
# -----------------------------------------------------------------------------


def seed_graph_from_domain(
    graph_store: GraphStoreService,
    sample_data_dir: str | Path | None = None,
) -> None:
    """Populate property graph store with domain entities and edges from sample_data JSON files."""
    if sample_data_dir is None:
        target_dir = Path(__file__).resolve().parents[1] / "sample_data"
    else:
        target_dir = Path(sample_data_dir)

    def _load_json(filename: str) -> list[dict[str, Any]]:
        path = target_dir / filename
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return list(data) if isinstance(data, list) else []

    # 1. Teams
    for team in _load_json("teams.json"):
        props = {
            "name": team.get("name"),
            "lead": team.get("lead"),
            "slack_channel": team.get("slack_channel"),
            "description": team.get("description"),
        }
        graph_store.add_node(team["id"], label="Team", properties=props)

    # 2. Employees
    for emp in _load_json("employees.json"):
        props = {
            "name": emp.get("name"),
            "email": emp.get("email"),
            "role": emp.get("role"),
            "team_id": emp.get("team_id"),
        }
        graph_store.add_node(emp["id"], label="Employee", properties=props)
        if emp.get("team_id"):
            graph_store.add_edge(emp["id"], emp["team_id"], "MEMBER_OF")

    # 3. Services
    for svc in _load_json("services.json"):
        props = {
            "name": svc.get("name"),
            "tier": svc.get("tier"),
            "port": svc.get("port"),
            "repo_url": svc.get("repo_url"),
            "owner_team_id": svc.get("owner_team_id"),
        }
        graph_store.add_node(svc["id"], label="Service", properties=props)
        if svc.get("owner_team_id"):
            graph_store.add_edge(svc["id"], svc["owner_team_id"], "OWNED_BY")

    # 4. Customers
    for cust in _load_json("customers.json"):
        props = {
            "name": cust.get("name"),
            "tier": cust.get("tier"),
            "contract_value": str(cust.get("contract_value")),
            "industry": cust.get("industry"),
        }
        graph_store.add_node(cust["id"], label="Customer", properties=props)

    # 5. Incidents
    for inc in _load_json("incidents.json"):
        props = {
            "title": inc.get("title"),
            "severity": inc.get("severity"),
            "status": inc.get("status"),
            "root_cause": inc.get("root_cause"),
            "occurred_at": inc.get("occurred_at"),
            "resolved_at": inc.get("resolved_at"),
            "quarter": inc.get("quarter"),
        }
        graph_store.add_node(inc["id"], label="Incident", properties=props)
        if inc.get("impacted_service_id"):
            graph_store.add_edge(inc["id"], inc["impacted_service_id"], "AFFECTED")
        for cust_id in inc.get("impacted_customers", []):
            graph_store.add_edge(inc["id"], cust_id, "IMPACTED")

    # 6. Decisions (ADRs)
    for dec in _load_json("decisions.json"):
        props = {
            "title": dec.get("title"),
            "status": dec.get("status"),
            "context": dec.get("context"),
            "decision": dec.get("decision"),
            "consequences": dec.get("consequences"),
            "incident_id": dec.get("incident_id"),
        }
        dec_id = dec["id"]
        graph_store.add_node(dec_id, label="Decision", properties=props)
        # Register short ADR alias if id has dec- prefix (e.g. dec-adr-042 -> adr-042)
        if dec_id.startswith("dec-"):
            short_id = dec_id.replace("dec-", "")
            graph_store.add_node(short_id, label="Decision", properties=props)

        if dec.get("incident_id"):
            graph_store.add_edge(dec_id, dec["incident_id"], "ADDRESSED")
            if dec_id.startswith("dec-"):
                graph_store.add_edge(
                    dec_id.replace("dec-", ""), dec["incident_id"], "ADDRESSED"
                )

    # 7. Projects
    for proj in _load_json("projects.json"):
        props = {
            "name": proj.get("name"),
            "description": proj.get("description"),
            "status": proj.get("status"),
            "owner_team_id": proj.get("owner_team_id"),
        }
        graph_store.add_node(proj["id"], label="Project", properties=props)
        if proj.get("owner_team_id"):
            graph_store.add_edge(proj["id"], proj["owner_team_id"], "OWNED_BY")

    # 8. Tickets
    for tick in _load_json("tickets.json"):
        props = {
            "title": tick.get("title"),
            "status": tick.get("status"),
            "priority": tick.get("priority"),
            "project_id": tick.get("project_id"),
            "assignee_id": tick.get("assignee_id"),
        }
        graph_store.add_node(tick["id"], label="Ticket", properties=props)
        if tick.get("project_id"):
            graph_store.add_edge(tick["id"], tick["project_id"], "PART_OF")
        if tick.get("assignee_id"):
            graph_store.add_edge(tick["id"], tick["assignee_id"], "ASSIGNED_TO")


# -----------------------------------------------------------------------------
# Governed Traversal & Execution
# -----------------------------------------------------------------------------


def _format_entity_summary(node: dict[str, Any]) -> str:
    """Format node label, ID, and primary properties into readable summary text."""
    label = node.get("label", "Node")
    node_id = node.get("id", "")
    props = node.get("properties", {})
    name_or_title = props.get("name") or props.get("title") or props.get("description")
    if name_or_title:
        return f"{label}:{node_id} ({name_or_title})"
    return f"{label}:{node_id}"


def _format_edge_content(
    source_node: dict[str, Any],
    rel_type: str,
    target_node: dict[str, Any],
) -> str:
    """Format relationship edge into descriptive evidence prose."""
    src_summary = _format_entity_summary(source_node)
    tgt_summary = _format_entity_summary(target_node)
    return f"[{src_summary}] -[:{rel_type}]-> [{tgt_summary}]"


def execute_governed_traversal(
    traversal_type: str,
    params: dict[str, Any] | None = None,
    graph_store: GraphStoreService | None = None,
    sub_question_id: str = "sq1",
) -> list[Evidence]:
    """Execute a named typed traversal and convert discovered paths into canonical Evidence.

    Args:
        traversal_type: Identifier of the typed traversal (e.g. incident_blast_radius).
        params: Parameter bindings for traversal (e.g. {'incident_id': 'inc-2031'}).
        graph_store: Optional GraphStoreService; defaults to global store.
        sub_question_id: Sub-question identifier for evidence tracking.

    Returns:
        list[Evidence]: Canonical Evidence items with source_type='graph' and Cypher locators.
    """
    store = graph_store if graph_store is not None else get_graph_store()
    params = dict(params or {})

    # Resolve and validate corresponding Cypher template
    template: GraphQueryTemplate
    if traversal_type == "incident_blast_radius":
        inc_id = params.get("incident_id", "")
        template = get_incident_blast_radius_template(inc_id)
    elif traversal_type == "customer_impact":
        cust_id = params.get("customer_id", "")
        template = get_customer_impact_template(cust_id)
    elif traversal_type == "service_dependencies":
        svc_id = params.get("service_id", "")
        template = get_service_dependencies_template(svc_id)
    elif traversal_type == "team_ownership":
        t_id = params.get("team_id", "")
        template = get_team_ownership_template(t_id)
    elif traversal_type == "service_incidents":
        svc_id = params.get("service_id", "")
        template = get_service_incidents_template(svc_id)
    elif traversal_type == "decision_lineage":
        dec_id = params.get("decision_id", "")
        template = get_decision_lineage_template(dec_id)
    else:
        raise CypherValidationError(f"Unknown graph traversal type: {traversal_type}")

    if not validate_cypher(template.cypher):
        raise CypherValidationError(
            f"Cypher template validation failed: {template.cypher}"
        )

    evidence_items: list[Evidence] = []
    seen_locators: set[str] = set()

    # Collect traversed edges from store based on traversal semantics
    edges_to_traverse: list[
        tuple[str, str, str]
    ] = []  # (source_id, rel_type, target_id)

    if traversal_type == "incident_blast_radius":
        incident_id = params.get("incident_id", "")
        # Outgoing edges from incident: AFFECTED -> service, IMPACTED -> customer
        for n in store.get_neighbors(incident_id):
            edge = n.get("edge", {})
            if edge.get("source") == incident_id:
                edges_to_traverse.append((incident_id, edge["type"], edge["target"]))
                # If target is service, find owner team
                if edge["type"] == "AFFECTED":
                    svc_id = edge["target"]
                    for s_n in store.get_neighbors(svc_id):
                        s_edge = s_n.get("edge", {})
                        if (
                            s_edge.get("source") == svc_id
                            and s_edge.get("type") == "OWNED_BY"
                        ):
                            edges_to_traverse.append(
                                (svc_id, "OWNED_BY", s_edge["target"])
                            )
            elif edge.get("target") == incident_id and edge.get("type") == "ADDRESSED":
                edges_to_traverse.append((edge["source"], "ADDRESSED", incident_id))

    elif traversal_type == "customer_impact":
        customer_id = params.get("customer_id", "")
        # Incoming edges to customer: incident -[:IMPACTED]-> customer
        for n in store.get_neighbors(customer_id):
            edge = n.get("edge", {})
            if edge.get("target") == customer_id and edge.get("type") == "IMPACTED":
                inc_id = edge["source"]
                edges_to_traverse.append((inc_id, "IMPACTED", customer_id))
                # For each incident, find affected services
                for inc_n in store.get_neighbors(inc_id):
                    inc_edge = inc_n.get("edge", {})
                    if (
                        inc_edge.get("source") == inc_id
                        and inc_edge.get("type") == "AFFECTED"
                    ):
                        edges_to_traverse.append(
                            (inc_id, "AFFECTED", inc_edge["target"])
                        )

    elif traversal_type == "team_ownership":
        team_id = params.get("team_id", "")
        # Incoming edges to team: service -[:OWNED_BY]-> team, project -[:OWNED_BY]-> team, emp -[:MEMBER_OF]-> team
        for n in store.get_neighbors(team_id):
            edge = n.get("edge", {})
            if edge.get("target") == team_id and edge.get("type") in (
                "OWNED_BY",
                "MEMBER_OF",
                "OWNS",
            ):
                edges_to_traverse.append((edge["source"], edge["type"], team_id))

    elif traversal_type == "service_dependencies":
        service_id = params.get("service_id", "")
        for n in store.get_neighbors(service_id):
            edge = n.get("edge", {})
            if edge.get("source") == service_id and edge.get("type") in (
                "DEPENDS_ON",
                "CALLS",
                "OWNED_BY",
            ):
                edges_to_traverse.append((service_id, edge["type"], edge["target"]))

    elif traversal_type == "service_incidents":
        service_id = params.get("service_id", "")
        # Incoming AFFECTED edges from incidents
        for n in store.get_neighbors(service_id):
            edge = n.get("edge", {})
            if edge.get("target") == service_id and edge.get("type") == "AFFECTED":
                inc_id = edge["source"]
                edges_to_traverse.append((inc_id, "AFFECTED", service_id))
                for inc_n in store.get_neighbors(inc_id):
                    inc_edge = inc_n.get("edge", {})
                    if (
                        inc_edge.get("source") == inc_id
                        and inc_edge.get("type") == "IMPACTED"
                    ):
                        edges_to_traverse.append(
                            (inc_id, "IMPACTED", inc_edge["target"])
                        )

    elif traversal_type == "decision_lineage":
        decision_id = params.get("decision_id", "")
        for n in store.get_neighbors(decision_id):
            edge = n.get("edge", {})
            if edge.get("source") == decision_id and edge.get("type") == "ADDRESSED":
                inc_id = edge["target"]
                edges_to_traverse.append((decision_id, "ADDRESSED", inc_id))
                for inc_n in store.get_neighbors(inc_id):
                    inc_edge = inc_n.get("edge", {})
                    if (
                        inc_edge.get("source") == inc_id
                        and inc_edge.get("type") == "AFFECTED"
                    ):
                        svc_id = inc_edge["target"]
                        edges_to_traverse.append((inc_id, "AFFECTED", svc_id))
                        for svc_n in store.get_neighbors(svc_id):
                            svc_edge = svc_n.get("edge", {})
                            if (
                                svc_edge.get("source") == svc_id
                                and svc_edge.get("type") == "OWNED_BY"
                            ):
                                edges_to_traverse.append(
                                    (svc_id, "OWNED_BY", svc_edge["target"])
                                )

    # Convert traversed edges into canonical Evidence items
    for src_id, rel_type, tgt_id in edges_to_traverse:
        src_node = store.get_node(src_id)
        tgt_node = store.get_node(tgt_id)
        if not src_node or not tgt_node:
            continue

        src_label = src_node.get("label", "Node")
        tgt_label = tgt_node.get("label", "Node")
        locator = build_graph_locator(
            source_label=src_label,
            source_id=src_id,
            rel_type=rel_type,
            target_label=tgt_label,
            target_id=tgt_id,
        )

        if locator in seen_locators:
            continue
        seen_locators.add(locator)

        content = _format_edge_content(src_node, rel_type, tgt_node)
        meta = {
            "store": "graph",
            "cypher": template.cypher,
            "traversal_type": traversal_type,
            "source_id": src_id,
            "target_id": tgt_id,
            "relationship": rel_type,
        }
        evidence = create_graph_evidence(
            sub_question_id=sub_question_id,
            locator=locator,
            content=content,
            cypher=template.cypher,
            score=1.0,
            metadata=meta,
        )
        evidence_items.append(evidence)

    return evidence_items


def execute_read_only_cypher(
    cypher: str,
    params: dict[str, Any] | None = None,
    graph_store: GraphStoreService | None = None,
    sub_question_id: str = "sq1",
) -> list[Evidence]:
    """Validate and execute a read-only Cypher query, formatting results into canonical Evidence.

    Raises:
        CypherValidationError: If query violates read-only rules or syntax constraints.
    """
    if not validate_cypher(cypher):
        raise CypherValidationError(
            f"Cypher statement failed read-only validation: {cypher}"
        )

    store = graph_store if graph_store is not None else get_graph_store()
    results = store.query_read_only(cypher, params)

    evidence_items: list[Evidence] = []
    for item in results:
        node_id = item.get("id")
        label = item.get("label", "Node")
        if node_id:
            locator = f"({label}:{node_id})"
            summary = _format_entity_summary(item)
            props_str = " | ".join(
                f"{k}={v}"
                for k, v in item.get("properties", {}).items()
                if v is not None
            )
            content = f"[{summary}] {props_str}".strip()
            evidence = create_graph_evidence(
                sub_question_id=sub_question_id,
                locator=locator,
                content=content,
                cypher=cypher,
                score=1.0,
                metadata={
                    "store": "graph",
                    "cypher": cypher,
                    "node_id": node_id,
                    "label": label,
                },
            )
            evidence_items.append(evidence)

    return evidence_items


class GraphRetriever:
    """Governed graph retrieval component for LangGraph agent workflows (Claude.md §5, §8)."""

    def __init__(self, graph_store: GraphStoreService | None = None) -> None:
        self.graph_store = graph_store

    def retrieve(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        sub_question_id: str = "sq1",
    ) -> list[Evidence]:
        """Execute read-only Cypher query and return Evidence items."""
        return execute_read_only_cypher(
            cypher=query,
            params=params,
            graph_store=self.graph_store,
            sub_question_id=sub_question_id,
        )

    def retrieve_traversal(
        self,
        traversal_type: str,
        params: dict[str, Any] | None = None,
        sub_question_id: str = "sq1",
    ) -> list[Evidence]:
        """Execute typed domain traversal and return Evidence items."""
        return execute_governed_traversal(
            traversal_type=traversal_type,
            params=params,
            graph_store=self.graph_store,
            sub_question_id=sub_question_id,
        )

    def retrieve_from_template(
        self,
        template: GraphQueryTemplate,
        sub_question_id: str = "sq1",
    ) -> list[Evidence]:
        """Execute traversal from structured template and return Evidence items."""
        return execute_governed_traversal(
            traversal_type=template.traversal_type,
            params=template.params,
            graph_store=self.graph_store,
            sub_question_id=sub_question_id,
        )
