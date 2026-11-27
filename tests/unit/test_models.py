"""Unit tests for SQLAlchemy domain and platform models (P2-1).

Verifies schema creation, entity relationships, constraints, monetary precision,
and JSON serialization across all domain and operational models.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from backend.app.models import (
    ApprovalRequest,
    AuditLog,
    Base,
    CitationRecord,
    Customer,
    Decision,
    Document,
    DocumentChunk,
    Employee,
    Incident,
    Project,
    ResearchSession,
    Service,
    Team,
    Ticket,
    User,
    WorkflowEvent,
)


@pytest.fixture(autouse=True)
def setup_database_tables(db_engine):
    """Create all tables before each test and drop them on teardown."""
    Base.metadata.create_all(bind=db_engine)
    yield
    Base.metadata.drop_all(bind=db_engine)


def test_metadata_contains_all_canonical_tables(db_engine):
    """Verify that SQLAlchemy metadata defines all required tables."""
    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "teams",
        "employees",
        "services",
        "customers",
        "incidents",
        "decisions",
        "projects",
        "tickets",
        "research_sessions",
        "workflow_events",
        "citation_records",
        "documents",
        "document_chunks",
        "approval_requests",
        "users",
        "audit_logs",
    }

    missing_tables = expected_tables - tables
    assert not missing_tables, f"Database is missing tables: {missing_tables}"


def test_team_and_employee_relationship(db_session: Session):
    """Test Team creation, Employee association, and bidirectional relationship."""
    team = Team(
        id="team-sre",
        name="Site Reliability Engineering",
        lead="Alice Zhang",
        slack_channel="#sre-oncall",
        description="Core infrastructure and platform reliability",
    )
    db_session.add(team)
    db_session.flush()

    emp1 = Employee(
        id="emp-101",
        name="Bob Smith",
        email="bob@example.com",
        role="Senior SRE",
        team_id=team.id,
    )
    emp2 = Employee(
        id="emp-102",
        name="Carol Danvers",
        email="carol@example.com",
        role="Staff Engineer",
        team_id=team.id,
    )
    db_session.add_all([emp1, emp2])
    db_session.commit()

    queried_team = db_session.get(Team, "team-sre")
    assert queried_team is not None
    assert len(queried_team.employees) == 2
    emp_names = {e.name for e in queried_team.employees}
    assert "Bob Smith" in emp_names
    assert "Carol Danvers" in emp_names
    assert emp1.team.name == "Site Reliability Engineering"


def test_service_and_incident_relationships(db_session: Session):
    """Test Service, Customer, Incident, and Decision relationships."""
    team = Team(id="team-payments", name="Payments Platform", lead="Diana Prince")
    db_session.add(team)

    service = Service(
        id="srv-payments-api",
        name="Payments API",
        tier="tier-1",
        port=8080,
        owner_team_id=team.id,
    )
    customer = Customer(
        id="cust-acme",
        name="Acme Corporation",
        tier="enterprise",
        contract_value=Decimal("250000.50"),
        industry="Retail",
    )
    db_session.add_all([service, customer])
    db_session.flush()

    incident = Incident(
        id="INC-2026-001",
        title="Payments API Connection Pool Exhaustion",
        severity="SEV-1",
        status="resolved",
        root_cause="Database connection pool limit exceeded under spike traffic.",
        impacted_service_id=service.id,
        occurred_at=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(incident)
    db_session.flush()

    decision = Decision(
        id="ADR-004",
        title="Dynamic Connection Pooling and Queue Throttling",
        status="accepted",
        context="INC-2026-001 exposed rigid pool limits under peak load.",
        decision="Adopt HikariCP with elastic scaling and token-bucket circuit breaker.",
        consequences="Mitigates thread starvation; introduces 50ms queue buffer.",
        incident_id=incident.id,
    )
    db_session.add(decision)
    db_session.commit()

    # Query and assert relationships
    q_service = db_session.get(Service, "srv-payments-api")
    assert q_service is not None
    assert len(q_service.incidents) == 1
    assert q_service.incidents[0].id == "INC-2026-001"
    assert q_service.owner_team is not None
    assert q_service.owner_team.name == "Payments Platform"

    q_incident = db_session.get(Incident, "INC-2026-001")
    assert q_incident is not None
    assert len(q_incident.decisions) == 1
    assert q_incident.decisions[0].id == "ADR-004"

    # Monetary precision check
    q_cust = db_session.get(Customer, "cust-acme")
    assert q_cust is not None
    assert q_cust.contract_value == Decimal("250000.50")


def test_project_and_ticket_relationship(db_session: Session):
    """Test Project and Ticket hierarchy with assignee link."""
    team = Team(id="team-data", name="Data Platform")
    emp = Employee(
        id="emp-201", name="Eve Green", email="eve@example.com", team_id=team.id
    )
    project = Project(
        id="proj-rag", name="Enterprise Knowledge Graph", owner_team_id=team.id
    )
    db_session.add_all([team, emp, project])
    db_session.flush()

    ticket = Ticket(
        id="TICK-101",
        title="Implement Typed Cypher Traversals",
        status="in_progress",
        priority="P1",
        project_id=project.id,
        assignee_id=emp.id,
    )
    db_session.add(ticket)
    db_session.commit()

    q_proj = db_session.get(Project, "proj-rag")
    assert q_proj is not None
    assert len(q_proj.tickets) == 1
    assert q_proj.tickets[0].assignee is not None
    assert q_proj.tickets[0].assignee.name == "Eve Green"


def test_research_session_and_events(db_session: Session):
    """Test ResearchSession, WorkflowEvent, and CitationRecord telemetry data models."""
    session_id = str(uuid.uuid4())
    session = ResearchSession(
        id=session_id,
        question="Which customers were impacted by the Payments API incident?",
        status="running",
        complexity="complex",
        sub_questions=[
            {
                "id": "sq1",
                "text": "Which services had SEV-1 incidents?",
                "strategy": "graph",
            },
            {
                "id": "sq2",
                "text": "What customers use Payments API?",
                "strategy": "sql",
            },
        ],
        evidence_data=[{"source": "sql", "rows": 5}],
        execution_time=1.45,
    )
    db_session.add(session)
    db_session.flush()

    event = WorkflowEvent(
        session_id=session.id,
        node_name="assess_complexity",
        event_type="node_complete",
        payload={"complexity": "complex", "routing": "hybrid"},
        latency_ms=120,
    )
    citation = CitationRecord(
        session_id=session.id,
        chunk_id="chk-991",
        document_id="doc-postmortem-01",
        locator="doc-postmortem-01#p4",
        text_snippet="Payments API latency breached SLA on 2026-01-15.",
        score=0.96,
    )
    db_session.add_all([event, citation])
    db_session.commit()

    q_session = db_session.get(ResearchSession, session_id)
    assert q_session is not None
    assert len(q_session.events) == 1
    assert q_session.events[0].node_name == "assess_complexity"
    assert len(q_session.citations) == 1
    assert q_session.citations[0].chunk_id == "chk-991"
    assert q_session.sub_questions[0]["id"] == "sq1"


def test_document_and_chunks(db_session: Session):
    """Test Document, DocumentChunk, and ApprovalRequest models."""
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="Q4_Payments_Postmortem.md",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        chunk_count=3,
        flagged_injection=False,
        status="indexed",
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        chunk_index=0,
        text="Executive Summary: Payments API downtime occurred on Jan 15.",
        embedding_id="vec-001",
        metadata_json={"section": "summary", "author": "Alice"},
    )
    chunk2 = DocumentChunk(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        chunk_index=1,
        text="Root cause identified as connection exhaustion in HikariCP.",
        embedding_id="vec-002",
        metadata_json={"section": "root_cause"},
    )
    db_session.add_all([chunk1, chunk2])

    approval = ApprovalRequest(
        id=str(uuid.uuid4()),
        resource_type="document",
        resource_id=doc.id,
        action="delete",
        requester_id="user-analyst-1",
        status="pending",
    )
    db_session.add(approval)
    db_session.commit()

    q_doc = db_session.get(Document, doc_id)
    assert q_doc is not None
    assert len(q_doc.chunks) == 2
    assert q_doc.chunks[0].chunk_index == 0
    assert q_doc.chunks[1].metadata_json["section"] == "root_cause"


def test_user_and_audit_log(db_session: Session):
    """Test User and append-only AuditLog models."""
    user = User(
        id=str(uuid.uuid4()),
        username="lead_analyst",
        email="analyst@enterprise.com",
        role="analyst",
        hashed_password="argon2$mocked$hash",
    )
    db_session.add(user)
    db_session.flush()

    audit = AuditLog(
        user_id=user.id,
        action="execute_research",
        resource_type="research_session",
        resource_id="session-xyz-123",
        request_id="req-trace-001",
        ip_address="127.0.0.1",
    )
    db_session.add(audit)
    db_session.commit()

    q_user = db_session.get(User, user.id)
    assert q_user is not None
    assert q_user.role == "analyst"

    audit_entry = (
        db_session.query(AuditLog).filter_by(request_id="req-trace-001").first()
    )
    assert audit_entry is not None
    assert audit_entry.action == "execute_research"
    assert audit_entry.user_id == user.id
