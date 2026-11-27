"""Unit tests for DB schema, Alembic migrations, and Supabase RLS policies (P2-2).

Verifies database engine/session lifecycle, Alembic migration upgrade/downgrade,
schema DDL, and Row-Level Security policy definitions.
"""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from backend.app.core.db import get_db, get_engine, get_session_factory, init_db


def test_db_core_engine_and_init():
    """Verify init_db initializes all tables and get_db yields an active session."""
    with NamedTemporaryFile(suffix=".db") as tmp_file:
        sqlite_url = f"sqlite:///{tmp_file.name}"
        engine = get_engine(sqlite_url)
        init_db(engine)

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert len(tables) >= 16
        assert "teams" in tables
        assert "research_sessions" in tables
        assert "audit_logs" in tables

        # Verify get_db generator
        session_gen = get_db(sqlite_url)
        session = next(session_gen)
        assert session.is_active
        res = session.execute(text("SELECT 1;")).scalar()
        assert res == 1
        with pytest.raises(StopIteration):
            next(session_gen)

    # Test default zero-argument invocation covering config resolution
    default_engine = get_engine()
    assert default_engine is not None
    factory = get_session_factory()
    assert factory is not None
    init_db()


def test_alembic_migrations_upgrade_and_downgrade():
    """Verify Alembic migration upgrade to head and downgrade to base."""
    alembic_ini_path = Path("alembic.ini")
    assert alembic_ini_path.exists(), "alembic.ini must exist at project root"

    with NamedTemporaryFile(suffix=".db") as tmp_file:
        sqlite_url = f"sqlite:///{tmp_file.name}"

        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)

        # 1. Upgrade to head
        command.upgrade(alembic_cfg, "head")

        engine = get_engine(sqlite_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        assert "alembic_version" in tables
        assert "teams" in tables
        assert "research_sessions" in tables
        assert "audit_logs" in tables
        assert "documents" in tables

        # 2. Downgrade to base
        command.downgrade(alembic_cfg, "base")

        inspector_downgraded = inspect(engine)
        tables_after_downgrade = set(inspector_downgraded.get_table_names())
        assert "teams" not in tables_after_downgrade
        assert "research_sessions" not in tables_after_downgrade


def test_rls_policies_file_specifications():
    """Verify database/rls_policies.sql exists, enables RLS, and defines RBAC policies."""
    rls_path = Path("database/rls_policies.sql")
    assert rls_path.exists(), "database/rls_policies.sql must exist"

    content = rls_path.read_text(encoding="utf-8")
    content_upper = content.upper()

    expected_tables = [
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
    ]

    # Verify RLS is enabled on all tables
    for table in expected_tables:
        assert (
            f"ALTER TABLE {table.upper()} ENABLE ROW LEVEL SECURITY" in content_upper
            or (
                f"ALTER TABLE ONLY {table.upper()} ENABLE ROW LEVEL SECURITY"
                in content_upper
            )
        ), f"Missing ENABLE ROW LEVEL SECURITY on table '{table}'"

    # Verify roles and security policies
    assert "SERVICE_ROLE" in content_upper
    assert "VIEWER" in content_upper
    assert "ANALYST" in content_upper
    assert "ADMIN" in content_upper

    # Verify append-only invariant on audit_logs
    assert "AUDIT_LOGS" in content_upper
    assert (
        "NO_UPDATE_AUDIT" in content_upper
        or "PROHIBIT_UPDATE" in content_upper
        or "FOR UPDATE USING (FALSE)" in content_upper
    )


def test_schema_sql_file_exists():
    """Verify database/schema.sql exists and contains table DDL definitions."""
    schema_path = Path("database/schema.sql")
    assert schema_path.exists(), "database/schema.sql must exist"

    content = schema_path.read_text(encoding="utf-8").upper()
    assert "CREATE TABLE" in content
    assert "TEAMS" in content
    assert "RESEARCH_SESSIONS" in content
