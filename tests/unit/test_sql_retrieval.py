"""Unit and integration tests for Governed SQL retrieval and templates (P6-2, F7).

Validates:
- Structured SQL query templates (customers, incidents, services, teams, decisions, projects, tickets)
- SQL retrieval execution on read-only database session
- Conversion of rows into canonical Evidence models with sql locator
- Rejection of invalid / malicious SQL with SQLValidationError
"""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from backend.app.core.db import get_engine, get_session_factory, init_db
from backend.app.schemas.common import Evidence
from backend.app.services.seed import seed_database
from rag.sql_retrieval import (
    SQLQueryTemplate,
    SQLRetriever,
    SQLValidationError,
    execute_governed_sql,
    get_customer_template,
    get_incident_template,
    get_service_template,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Initialize SQLite database with seeded sample data for SQL retrieval tests."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
        yield session


def test_sql_query_templates_format() -> None:
    """Verify built-in SQL templates format correctly into valid parameterized SQL."""
    # Customer template
    t1 = get_customer_template(tier="enterprise")
    assert isinstance(t1, SQLQueryTemplate)
    assert "FROM customers" in t1.query
    assert "tier = :tier" in t1.query
    assert t1.params == {"tier": "enterprise"}

    # Incident template
    t2 = get_incident_template(severity="SEV1")
    assert "FROM incidents" in t2.query
    assert "severity = :severity" in t2.query
    assert t2.params == {"severity": "SEV1"}

    # Service template
    t3 = get_service_template(service_id="svc-payments-api")
    assert "FROM services" in t3.query
    assert "id = :service_id" in t3.query
    assert t3.params == {"service_id": "svc-payments-api"}


def test_execute_governed_sql_returns_evidence(db_session: Session) -> None:
    """Verify execute_governed_sql queries database and produces valid Evidence items."""
    sql = "SELECT id, name, tier, contract_value, industry FROM customers WHERE tier = 'enterprise'"
    evidence_items = execute_governed_sql(
        sql_str=sql,
        db=db_session,
        sub_question_id="sq_sql_1",
    )

    assert isinstance(evidence_items, list)
    assert len(evidence_items) > 0

    first = evidence_items[0]
    assert isinstance(first, Evidence)
    assert first.source_type == "sql"
    assert first.sub_question_id == "sq_sql_1"
    assert first.locator.startswith("sql:customers:")
    assert "Acme" in first.content or "enterprise" in first.content
    assert first.score == 1.0
    assert first.metadata["table"] == "customers"
    assert first.metadata["sql_query"] == sql


def test_execute_governed_sql_with_params(db_session: Session) -> None:
    """Verify parameterized query execution prevents injection while returning evidence."""
    sql = "SELECT id, title, severity, status FROM incidents WHERE severity = :severity"
    params = {"severity": "SEV1"}

    evidence_items = execute_governed_sql(
        sql_str=sql,
        params=params,
        db=db_session,
        sub_question_id="sq_sql_2",
    )

    assert len(evidence_items) >= 1
    for evi in evidence_items:
        assert evi.source_type == "sql"
        assert evi.locator.startswith("sql:incidents:")
        assert "SEV1" in evi.content


def test_execute_governed_sql_rejects_malicious_query(db_session: Session) -> None:
    """Verify execute_governed_sql raises SQLValidationError for unvalidated statements."""
    malicious = "DROP TABLE customers"
    with pytest.raises(SQLValidationError):
        execute_governed_sql(sql_str=malicious, db=db_session)

    forbidden_table = "SELECT * FROM users"
    with pytest.raises(SQLValidationError):
        execute_governed_sql(sql_str=forbidden_table, db=db_session)


def test_sql_retriever_class_interface(db_session: Session) -> None:
    """Verify SQLRetriever class satisfies retrieval interface."""
    retriever = SQLRetriever(db=db_session)

    # 1. Direct query
    res = retriever.retrieve(
        query="SELECT id, name FROM services WHERE tier = 'tier-1'",
        sub_question_id="sq_svc",
    )
    assert len(res) > 0
    assert all(e.source_type == "sql" for e in res)

    # 2. Template execution
    tmpl = get_customer_template(name="Acme Corp")
    res_tmpl = retriever.retrieve_from_template(tmpl, sub_question_id="sq_acme")
    assert len(res_tmpl) == 1
    assert "Acme Corp" in res_tmpl[0].content
    assert res_tmpl[0].locator == "sql:customers:cust-acme"
