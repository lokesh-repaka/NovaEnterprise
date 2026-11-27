"""Unit tests for sample data bootstrap, seeding, and fiscal calendar resolution (P2-4)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.base import Base
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
from backend.app.services.seed import (
    get_fiscal_calendar,
    load_all_documents,
    load_json_data,
    resolve_fiscal_quarter,
    seed_database,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session fixture for seed tests."""
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


def test_sample_data_files_exist_and_counts():
    """Verify that all canonical JSON files and document files exist with exact entity counts."""
    base_dir = Path(__file__).resolve().parents[2] / "sample_data"
    assert base_dir.exists(), "sample_data directory must exist"

    # Verify counts in raw JSON files
    with open(base_dir / "teams.json", encoding="utf-8") as f:
        teams = json.load(f)
        assert len(teams) == 6

    with open(base_dir / "employees.json", encoding="utf-8") as f:
        employees = json.load(f)
        assert len(employees) == 20

    with open(base_dir / "services.json", encoding="utf-8") as f:
        services = json.load(f)
        assert len(services) == 8

    with open(base_dir / "customers.json", encoding="utf-8") as f:
        customers = json.load(f)
        assert len(customers) == 10

    with open(base_dir / "incidents.json", encoding="utf-8") as f:
        incidents = json.load(f)
        assert len(incidents) == 12

    with open(base_dir / "decisions.json", encoding="utf-8") as f:
        decisions = json.load(f)
        assert len(decisions) == 8

    with open(base_dir / "projects.json", encoding="utf-8") as f:
        projects = json.load(f)
        assert len(projects) == 6

    with open(base_dir / "tickets.json", encoding="utf-8") as f:
        tickets = json.load(f)
        assert len(tickets) == 15

    with open(base_dir / "organizational_memory.json", encoding="utf-8") as f:
        org_memory = json.load(f)
        assert "fiscal_calendar" in org_memory
        cal = org_memory["fiscal_calendar"]
        assert cal["current_quarter"] == "2026-Q3"
        assert cal["last_quarter"] == "2026-Q2"
        assert len(cal["quarters"]) == 4

    # Verify 15 markdown documents in sample_data/documents/
    doc_dir = base_dir / "documents"
    assert doc_dir.exists()
    docs = list(doc_dir.glob("*.md"))
    assert len(docs) == 15

    doc_names = [d.name for d in docs]
    assert "postmortem-inc-2031-payments-api-outage.md" in doc_names
    assert "vendor-note-processor-update.md" in doc_names

    # Check vendor note prompt injection payload
    vendor_note = (doc_dir / "vendor-note-processor-update.md").read_text(
        encoding="utf-8"
    )
    assert "<system>" in vendor_note
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in vendor_note


def test_seed_database_and_idempotence(db_session):
    """Verify that seed_database populates all entities and is strictly idempotent."""
    counts = seed_database(db_session)
    assert counts == {
        "teams": 6,
        "employees": 20,
        "services": 8,
        "customers": 10,
        "incidents": 12,
        "decisions": 8,
        "projects": 6,
        "tickets": 15,
    }

    # Verify database contents
    assert db_session.query(Team).count() == 6
    assert db_session.query(Employee).count() == 20
    assert db_session.query(Service).count() == 8
    assert db_session.query(Customer).count() == 10
    assert db_session.query(Incident).count() == 12
    assert db_session.query(Decision).count() == 8
    assert db_session.query(Project).count() == 6
    assert db_session.query(Ticket).count() == 15

    # Verify relations: INC-2031 impacts Payments API
    inc_2031 = db_session.get(Incident, "inc-2031")
    assert inc_2031 is not None
    assert inc_2031.impacted_service_id == "svc-payments-api"
    assert inc_2031.severity == "SEV1"

    # Verify that raw incident json contains the graph customer relationships
    raw_incidents = load_json_data("incidents.json")
    inc_2031_raw = next(i for i in raw_incidents if i["id"] == "inc-2031")
    assert set(inc_2031_raw["impacted_customers"]) == {
        "cust-acme",
        "cust-globex",
        "cust-wayne",
    }

    # Verify ADR-042 references INC-2031
    adr_42 = db_session.get(Decision, "dec-adr-042")
    assert adr_42 is not None
    assert adr_42.incident_id == "inc-2031"

    # Second run for idempotency
    counts_run2 = seed_database(db_session)
    assert counts_run2 == counts
    assert db_session.query(Team).count() == 6
    assert db_session.query(Incident).count() == 12


def test_fiscal_calendar_resolution():
    """Verify fiscal quarter resolution for natural language phrases."""
    # Last quarter -> 2026-Q2
    start, end, label = resolve_fiscal_quarter("last quarter")
    assert label == "2026-Q2"
    assert start == datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

    # Previous quarter -> 2026-Q2
    start_p, end_p, label_p = resolve_fiscal_quarter("previous quarter")
    assert label_p == "2026-Q2"
    assert start_p == start
    assert end_p == end

    # Current quarter -> 2026-Q3
    start_curr, end_curr, label_curr = resolve_fiscal_quarter("current quarter")
    assert label_curr == "2026-Q3"
    assert start_curr == datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end_curr == datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)

    # Explicit quarter label
    start_q1, end_q1, label_q1 = resolve_fiscal_quarter("2026-Q1")
    assert label_q1 == "2026-Q1"
    assert start_q1 == datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end_q1 == datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc)

    # Invalid quarter
    with pytest.raises(ValueError, match="Could not resolve fiscal quarter"):
        resolve_fiscal_quarter("unknown interval")


def test_load_all_documents(tmp_path):
    """Verify loading documents with prompt injection quarantine tagging."""
    docs = load_all_documents()
    assert len(docs) == 15

    # Check that vendor-note is flagged
    vendor_docs = [
        d for d in docs if d["filename"] == "vendor-note-processor-update.md"
    ]
    assert len(vendor_docs) == 1
    assert vendor_docs[0]["is_untrusted"] is True
    assert vendor_docs[0]["flagged_injection"] is True

    # Check normal postmortem is not flagged
    postmortem_docs = [
        d for d in docs if d["filename"] == "postmortem-inc-2031-payments-api-outage.md"
    ]
    assert len(postmortem_docs) == 1
    assert postmortem_docs[0]["is_untrusted"] is False
    assert postmortem_docs[0]["flagged_injection"] is False

    # Documents dir missing
    with pytest.raises(FileNotFoundError, match="Documents directory not found"):
        load_all_documents(sample_data_dir=tmp_path)


def test_load_json_data_and_get_fiscal_calendar(tmp_path):
    """Verify load_json_data and get_fiscal_calendar helpers."""
    base_dir = Path(__file__).resolve().parents[2] / "sample_data"
    cal = get_fiscal_calendar(sample_data_dir=base_dir)
    assert cal["fiscal_year"] == 2026
    assert cal["current_quarter"] == "2026-Q3"

    teams = load_json_data("teams.json", sample_data_dir=str(base_dir))
    assert isinstance(teams, list)
    assert len(teams) == 6

    with pytest.raises(FileNotFoundError):
        load_json_data("non_existent_file.json")
