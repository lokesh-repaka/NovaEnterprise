"""Unit tests for the repository layer (P2-3).

Validates base CRUD operations, domain query filters, pagination, relationship eager loading,
research telemetry tracking, document management, and immutable audit logging.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.base import Base
from backend.app.models.documents import Document, DocumentChunk
from backend.app.models.domain import (
    Customer,
    Decision,
    Employee,
    Incident,
    Project,
    Service,
    Team,
    Ticket,
)
from backend.app.models.security import User
from backend.app.repositories import (
    ApprovalRequestRepository,
    AuditLogRepository,
    BaseRepository,
    CitationRecordRepository,
    CustomerRepository,
    DecisionRepository,
    DocumentChunkRepository,
    DocumentRepository,
    EmployeeRepository,
    IncidentRepository,
    ProjectRepository,
    ResearchSessionRepository,
    ServiceRepository,
    TeamRepository,
    TicketRepository,
    UserRepository,
    WorkflowEventRepository,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session fixture for repository tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_base_repository_crud(db_session):
    """Test standard generic CRUD on BaseRepository."""
    repo = BaseRepository[Team](Team, db_session)

    # Create
    team = Team(
        id="team-core",
        name="Core Infrastructure",
        lead="Dave Admin",
        description="Platform team",
    )
    created = repo.create(team)
    assert created.id == "team-core"

    # Get
    fetched = repo.get("team-core")
    assert fetched is not None
    assert fetched.name == "Core Infrastructure"

    # Count
    assert repo.count() == 1

    # List & pagination
    team2 = Team(
        id="team-sec",
        name="Security Engineering",
        lead="Eve Sec",
        description="Security team",
    )
    repo.create(team2)
    assert repo.count() == 2
    listed = repo.list(skip=0, limit=1, order_by=Team.name)
    assert len(listed) == 1
    assert listed[0].name == "Core Infrastructure"

    desc_list = repo.list(order_by=Team.name, descending=True)
    assert desc_list[0].name == "Security Engineering"

    # Update
    team.description = "Updated platform team"
    updated = repo.update(team)
    assert updated.description == "Updated platform team"

    # Save
    team.lead = "David Admin"
    saved = repo.save(team)
    assert saved.lead == "David Admin"

    # Delete by entity
    repo.delete(team2)
    assert repo.count() == 1

    # Delete by ID
    deleted = repo.delete_by_id("team-core")
    assert deleted is True
    assert repo.count() == 0
    assert repo.get("team-core") is None
    assert repo.delete_by_id("non-existent") is False


def test_team_and_employee_repositories(db_session):
    """Test TeamRepository and EmployeeRepository domain queries."""
    team_repo = TeamRepository(db_session)
    emp_repo = EmployeeRepository(db_session)

    team = team_repo.create(
        Team(
            id="team-pay",
            name="Payments Platform",
            lead="Alice Chen",
            description="Payments ownership",
        )
    )
    assert team.id == "team-pay"
    assert team_repo.get_by_name("Payments Platform") is not None
    assert team_repo.get_by_name("Non-Existent") is None

    emp1 = emp_repo.create(
        Employee(
            id="emp-1",
            name="Alice Chen",
            email="alice@nova.io",
            role="Staff Engineer",
            team_id="team-pay",
        )
    )
    emp2 = emp_repo.create(
        Employee(
            id="emp-2",
            name="Bob Martin",
            email="bob@nova.io",
            role="Senior Engineer",
            team_id="team-pay",
        )
    )
    assert emp2.id == "emp-2"

    assert emp_repo.get_by_email("alice@nova.io") == emp1
    assert emp_repo.get_by_email("nobody@nova.io") is None

    team_members = emp_repo.list_by_team("team-pay")
    assert len(team_members) == 2

    # Eager loading relations
    team_with_rels = team_repo.get_with_relations("team-pay")
    assert team_with_rels is not None
    assert len(team_with_rels.employees) == 2


def test_service_and_customer_repositories(db_session):
    """Test ServiceRepository and CustomerRepository operations."""
    service_repo = ServiceRepository(db_session)
    customer_repo = CustomerRepository(db_session)

    svc = service_repo.create(
        Service(
            id="svc-pay",
            name="Payments API",
            tier="tier-1",
            port=8001,
            repo_url="https://github.com/nova/payments",
        )
    )
    assert service_repo.get_by_name("Payments API") == svc
    assert len(service_repo.list_by_tier("tier-1")) == 1
    assert len(service_repo.list_by_tier("tier-2")) == 0
    assert len(service_repo.list_by_team("team-pay")) == 0

    cust = customer_repo.create(
        Customer(
            id="cust-acme",
            name="Acme Corp",
            tier="enterprise",
            contract_value=Decimal("1200000.00"),
            industry="Fintech",
        )
    )
    assert customer_repo.get_by_name("Acme Corp") == cust
    assert len(customer_repo.list_by_tier("enterprise")) == 1
    assert len(customer_repo.list_by_industry("Fintech")) == 1
    assert len(customer_repo.list_by_industry("Healthcare")) == 0


def test_incident_and_decision_repositories(db_session):
    """Test IncidentRepository, relations, and DecisionRepository."""
    service_repo = ServiceRepository(db_session)
    incident_repo = IncidentRepository(db_session)
    decision_repo = DecisionRepository(db_session)

    service_repo.create(Service(id="svc-pay", name="Payments API", tier="tier-1"))

    t0 = datetime(2026, 10, 15, 14, 30, tzinfo=timezone.utc)
    incident = incident_repo.create(
        Incident(
            id="inc-2031",
            title="INC-2031: Payments API Latency Spike",
            severity="SEV1",
            status="resolved",
            impacted_service_id="svc-pay",
            root_cause="Database connection pool exhaustion",
            occurred_at=t0,
        )
    )

    # Query with relationships
    inc_with_rels = incident_repo.get_with_relations("inc-2031")
    assert inc_with_rels is not None
    assert inc_with_rels.impacted_service is not None
    assert inc_with_rels.impacted_service.id == "svc-pay"

    # Search filters
    assert (
        incident_repo.get_by_title("INC-2031: Payments API Latency Spike") == incident
    )
    assert len(incident_repo.list_by_service("svc-pay")) == 1
    assert len(incident_repo.list_by_severity("SEV1")) == 1
    assert len(incident_repo.list_by_status("resolved")) == 1

    date_results = incident_repo.list_by_date_range(
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 10, 31, tzinfo=timezone.utc),
    )
    assert len(date_results) == 1

    # Decisions
    decision = decision_repo.create(
        Decision(
            id="dec-adr-042",
            title="ADR-042: Adopt PgBouncer for Connection Pooling",
            status="approved",
            incident_id="inc-2031",
            context="Incident INC-2031 caused connection pool exhaustion.",
            decision="Deploy PgBouncer as a sidecar for all tier-1 services.",
            consequences="Lower idle connection count and zero connection spikes.",
        )
    )
    assert (
        decision_repo.get_by_title("ADR-042: Adopt PgBouncer for Connection Pooling")
        == decision
    )
    assert len(decision_repo.list_by_incident("inc-2031")) == 1
    assert len(decision_repo.list_by_status("approved")) == 1


def test_project_and_ticket_repositories(db_session):
    """Test ProjectRepository and TicketRepository."""
    project_repo = ProjectRepository(db_session)
    ticket_repo = TicketRepository(db_session)

    proj = project_repo.create(
        Project(id="proj-db", name="DB Pool Optimization", status="active")
    )
    assert proj.id == "proj-db"
    assert len(project_repo.list_by_status("active")) == 1
    assert len(project_repo.list_by_team("team-core")) == 0

    ticket = ticket_repo.create(
        Ticket(
            id="tick-101",
            title="PAY-101: Tune pool size parameters",
            status="open",
            priority="P1",
            project_id="proj-db",
        )
    )
    assert ticket.id == "tick-101"
    assert len(ticket_repo.list_by_project("proj-db")) == 1
    assert len(ticket_repo.list_by_status("open")) == 1
    assert len(ticket_repo.list_by_priority("P1")) == 1
    assert len(ticket_repo.list_by_assignee("emp-none")) == 0


def test_research_telemetry_repositories(db_session):
    """Test ResearchSession, WorkflowEvent, and CitationRecord repositories."""
    session_repo = ResearchSessionRepository(db_session)
    event_repo = WorkflowEventRepository(db_session)
    citation_repo = CitationRecordRepository(db_session)

    # ResearchSession
    session = session_repo.create_session(
        question="Impact of Payments API outage", complexity="complex"
    )
    assert session.status == "running"
    assert session.complexity == "complex"

    active_sessions = session_repo.list_active()
    assert len(active_sessions) == 1
    assert len(session_repo.list_recent()) == 1

    # Update status
    updated_session = session_repo.update_status(
        session_id=session.id,
        status="completed",
        answer="Payments API outage impacted 2 enterprise clients.",
        execution_time=2.45,
    )
    assert updated_session is not None
    assert updated_session.status == "completed"
    assert updated_session.answer is not None
    assert session_repo.update_status("non-existent-id", status="completed") is None
    assert len(session_repo.list_active()) == 0

    # WorkflowEvent
    event1 = event_repo.record_event(
        session_id=session.id,
        node_name="analyze_query",
        event_type="node_complete",
        payload={"intent": "incident_impact"},
        latency_ms=45,
    )
    event2 = event_repo.record_event(
        session_id=session.id,
        node_name="assess_complexity",
        event_type="node_complete",
        payload={"complexity": "complex"},
        latency_ms=25,
    )
    assert event1.node_name == "analyze_query"
    assert event2.node_name == "assess_complexity"
    assert event_repo.count_by_session(session.id) == 2
    events = event_repo.list_by_session(session.id)
    assert len(events) == 2
    assert events[0].node_name == "analyze_query"
    desc_events = event_repo.list_by_session(session.id, order_asc=False)
    assert desc_events[0].node_name == "assess_complexity"

    # CitationRecord
    citation = citation_repo.record_citation(
        session_id=session.id,
        chunk_id="chk-1",
        document_id="doc-postmortem",
        locator="Section 3.2",
        text_snippet="INC-2031 occurred at 2026-10-15.",
        score=1.0,
    )
    assert citation.id is not None
    citations = citation_repo.list_by_session(session.id)
    assert len(citations) == 1


def test_document_and_approval_repositories(db_session):
    """Test Document, DocumentChunk, and ApprovalRequest repositories."""
    doc_repo = DocumentRepository(db_session)
    chunk_repo = DocumentChunkRepository(db_session)
    approval_repo = ApprovalRequestRepository(db_session)

    # Document
    doc = doc_repo.create(
        Document(
            id="doc-postmortem",
            filename="postmortem-inc-2031.md",
            content_hash="abc123sha",
            chunk_count=2,
            flagged_injection=False,
            status="indexed",
        )
    )
    assert doc_repo.get_by_filename("postmortem-inc-2031.md") == doc
    assert doc_repo.get_by_hash("abc123sha") == doc
    assert len(doc_repo.list_by_status("indexed")) == 1

    # Injection flagging
    flagged = doc_repo.mark_injection(doc.id, flagged=True)
    assert flagged is not None
    assert flagged.flagged_injection is True
    assert len(doc_repo.list_flagged_injections()) == 1
    assert doc_repo.mark_injection("non-existent-doc") is None

    # Chunks
    chunks = [
        DocumentChunk(
            id="chk-1", document_id=doc.id, chunk_index=0, text="Summary chunk"
        ),
        DocumentChunk(
            id="chk-2", document_id=doc.id, chunk_index=1, text="Root cause chunk"
        ),
    ]
    chunk_repo.create_chunks(chunks)
    assert len(chunk_repo.list_by_document(doc.id)) == 2

    # Delete chunks
    deleted_count = chunk_repo.delete_by_document(doc.id)
    assert deleted_count == 2
    assert len(chunk_repo.list_by_document(doc.id)) == 0
    assert chunk_repo.delete_by_document("non-existent-doc") == 0

    # Approval Request
    req = approval_repo.create_request(
        resource_type="document",
        resource_id=doc.id,
        requester_id="analyst-1",
        action="delete",
    )
    assert req.status == "pending"
    assert len(approval_repo.list_pending()) == 1

    resolved = approval_repo.resolve_request(
        req.id, status="approved", decided_by="admin-1"
    )
    assert resolved is not None
    assert resolved.status == "approved"
    assert resolved.decided_by == "admin-1"
    assert len(approval_repo.list_pending()) == 0
    assert (
        approval_repo.resolve_request(
            "unknown-appr", status="rejected", decided_by="admin-1"
        )
        is None
    )


def test_user_and_audit_log_repositories(db_session):
    """Test UserRepository and AuditLogRepository immutable constraints."""
    user_repo = UserRepository(db_session)
    audit_repo = AuditLogRepository(db_session)

    user = user_repo.create(
        User(
            id="usr-1",
            username="analyst_alice",
            email="alice@nova.io",
            role="analyst",
            hashed_password="hashed_pw_test",
        )
    )
    assert user_repo.get_by_username("analyst_alice") == user
    assert user_repo.get_by_email("alice@nova.io") == user
    assert len(user_repo.list_by_role("analyst")) == 1

    # AuditLog append-only logging
    log_entry = audit_repo.record_log(
        action="user_login",
        resource_type="auth",
        resource_id="usr-1",
        user_id="usr-1",
        request_id="req-test-123",
        ip_address="127.0.0.1",
    )
    assert log_entry.id is not None
    assert audit_repo.count_logs() == 1
    assert audit_repo.count_logs(resource_type="auth") == 1
    assert audit_repo.count_logs(user_id="usr-1") == 1
    assert len(audit_repo.list_logs(resource_type="auth")) == 1
    assert len(audit_repo.list_logs(user_id="usr-1")) == 1

    # Invariant: Audit logs are strictly immutable and append-only
    with pytest.raises(
        PermissionError, match="Audit logs are strictly append-only and immutable"
    ):
        audit_repo.update(log_entry)

    with pytest.raises(
        PermissionError, match="Audit logs are strictly append-only and immutable"
    ):
        audit_repo.delete(log_entry)

    with pytest.raises(
        PermissionError, match="Audit logs are strictly append-only and immutable"
    ):
        audit_repo.delete_by_id(log_entry.id)
