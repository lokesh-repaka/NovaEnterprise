"""Governed SQL retrieval, validation, and structured templates (P6-2, F7, Claude.md §5, §9).

Provides:
- Strict AST SQL validator (validate_sql) blocking injection, DDL/DML, system functions,
  and enforcing table allowlists.
- Canonical domain query templates (customers, incidents, services, teams, decisions, projects, tickets, employees).
- Governed execution yielding canonical Evidence instances with sql locators.
- SQLRetriever class encapsulating governed retrieval for LangGraph agent integration.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlparse  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlparse.sql import (  # type: ignore[import-untyped]
    Function,
    Identifier,
    IdentifierList,
    Parenthesis,
    Where,
)
from sqlparse.tokens import (  # type: ignore[import-untyped]
    DDL,
    DML,
    Comment,
    Keyword,
)

from backend.app.schemas.common import Evidence
from rag.evidence import create_sql_evidence

__all__ = [
    "ALLOWLISTED_TABLES",
    "DANGEROUS_FUNCTIONS",
    "DANGEROUS_KEYWORDS",
    "SQLQueryTemplate",
    "SQLRetriever",
    "SQLValidationError",
    "execute_governed_sql",
    "get_customer_template",
    "get_decision_template",
    "get_employee_template",
    "get_incident_template",
    "get_project_template",
    "get_service_template",
    "get_team_template",
    "get_ticket_template",
    "validate_sql",
]

ALLOWLISTED_TABLES: frozenset[str] = frozenset(
    {
        "incidents",
        "services",
        "teams",
        "customers",
        "decisions",
        "projects",
        "tickets",
        "employees",
    }
)

DANGEROUS_KEYWORDS: frozenset[str] = frozenset(
    {
        "DROP",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "DELETE",
        "UPDATE",
        "INSERT",
        "REPLACE",
        "EXEC",
        "EXECUTE",
        "PRAGMA",
        "ATTACH",
        "DETACH",
        "GRANT",
        "REVOKE",
        "VACUUM",
        "MERGE",
        "CALL",
        "INTO OUTFILE",
        "INTO DUMPFILE",
    }
)

DANGEROUS_FUNCTIONS: frozenset[str] = frozenset(
    {
        "benchmark",
        "char",
        "current_user",
        "database",
        "eval",
        "exec",
        "execute",
        "load_extension",
        "pg_read_file",
        "pg_sleep",
        "readfile",
        "schema",
        "session_user",
        "sleep",
        "system",
        "user",
        "version",
        "writefile",
        "xp_cmdshell",
    }
)


class SQLValidationError(Exception):
    """Raised when an SQL query fails security or allowlist validation."""


def _extract_tables_from_tokens(tokens: Sequence[Any]) -> set[str]:
    """Recursively extract referenced table names from SQL parse tokens."""
    tables: set[str] = set()
    from_seen = False

    for token in tokens:
        if isinstance(token, (Parenthesis, Where)):
            tables.update(_extract_tables_from_tokens(token.tokens))
        elif token.is_whitespace or token.ttype in (
            Comment,
            Comment.Single,
            Comment.Multiline,
        ):
            continue
        elif token.ttype is Keyword and token.value.upper() in (
            "FROM",
            "JOIN",
            "INNER JOIN",
            "LEFT JOIN",
            "RIGHT JOIN",
            "FULL JOIN",
            "CROSS JOIN",
            "NATURAL JOIN",
            "OUTER JOIN",
        ):
            from_seen = True
            continue
        elif from_seen:
            if isinstance(token, IdentifierList):
                for iden in token.get_identifiers():
                    parent = iden.get_parent_name()
                    real = iden.get_real_name() or iden.get_name()
                    if parent:
                        tables.add(f"{parent}.{real}".lower())
                    elif real:
                        tables.add(real.lower())
                from_seen = False
            elif isinstance(token, Identifier):
                parent = token.get_parent_name()
                real = token.get_real_name() or token.get_name()
                if parent:
                    tables.add(f"{parent}.{real}".lower())
                elif real:
                    tables.add(real.lower())
                from_seen = False
            elif token.ttype is Keyword or isinstance(token, Function):
                from_seen = False
            else:
                val = str(token.value).strip("`'\"")
                if val and not val.startswith(("(", ")", ";", ",")):
                    tables.add(val.lower())
                from_seen = False
    return tables


def _detect_primary_table(
    statement: sqlparse.sql.Statement, default: str = "records"
) -> str:
    """Detect the primary queried table from the FROM clause."""
    from_seen = False
    for token in statement.tokens:
        if token.is_whitespace:
            continue
        if token.ttype is Keyword and token.value.upper() == "FROM":
            from_seen = True
            continue
        if from_seen:
            if isinstance(token, IdentifierList):
                first_iden = next(token.get_identifiers(), None)
                if first_iden:
                    name = first_iden.get_real_name() or first_iden.get_name()
                    if name:
                        return str(name).lower()
            elif isinstance(token, Identifier):
                name = token.get_real_name() or token.get_name()
                if name:
                    return str(name).lower()
            else:
                val = str(token.value).strip("`'\"")
                if val and not val.startswith(("(", ")", ";", ",")):
                    return val.lower()
            break
    # Fallback to any extracted table
    all_tables = _extract_tables_from_tokens(statement.tokens)
    if all_tables:
        return min(all_tables)
    return default


def validate_sql(
    sql_str: str,
    allowlist: set[str] | frozenset[str] | None = None,
) -> bool:
    """Validate that an SQL query is a single read-only SELECT statement referencing allowlisted tables.

    Rules enforced:
    1. Read-only SELECT on allowlisted table succeeds.
    2. Multi-table JOIN on allowlisted tables succeeds.
    3. Semicolon injection and multi-statement execution is blocked.
    4. Destructive DDL statements (DROP, TRUNCATE, ALTER, CREATE) are blocked.
    5. Destructive DML statements (DELETE, UPDATE, INSERT) are blocked.
    6. Non-allowlisted / sensitive tables (users, audit_logs, sqlite_master) are blocked.
    7. Dangerous functions and shell execution commands are blocked.
    8. Empty, whitespace-only, comment-only, or syntactically invalid queries are blocked.
    """
    if not isinstance(sql_str, str):
        return False

    cleaned = sql_str.strip()
    if not cleaned:
        return False

    # Block comment-only inputs
    if cleaned.startswith(("--", "/*")):
        uncommented = sqlparse.format(cleaned, strip_comments=True).strip()
        if not uncommented:
            return False

    allowed_schema = frozenset(
        t.lower() for t in (allowlist if allowlist is not None else ALLOWLISTED_TABLES)
    )

    try:
        parsed = sqlparse.parse(cleaned)
    except Exception:  # noqa: BLE001 - malformed SQL strings can trigger unexpected parsing exceptions
        return False

    if not parsed:
        return False

    # Filter out empty statements from trailing semicolon
    non_empty_stmts = [s for s in parsed if str(s).strip().strip(";").strip()]
    if len(non_empty_stmts) != 1:
        return False

    statement = non_empty_stmts[0]

    # Statement type must be SELECT
    if statement.get_type() != "SELECT":
        return False

    # Token-level inspection for comments, forbidden keywords, and dangerous functions
    for token in statement.flatten():
        # Block comments in queries to prevent comment-based truncation bypasses
        if token.ttype in (Comment, Comment.Single, Comment.Multiline):
            return False

        val_upper = str(token.value).upper()

        # Block dangerous DDL / DML and admin commands
        if token.ttype in (Keyword, Keyword.DDL, Keyword.DML, DDL, DML):
            if val_upper in DANGEROUS_KEYWORDS:
                return False
            if token.ttype is Keyword.DML and val_upper not in (
                "SELECT",
                "WHERE",
                "FROM",
                "JOIN",
                "UNION",
                "AS",
                "ON",
            ):
                return False

        # Block dangerous system procedures and extension loaders
        if val_upper.lower() in DANGEROUS_FUNCTIONS:
            return False

    # Structural check: must contain SELECT followed by FROM with selected expressions
    significant_tokens = [
        t
        for t in statement.tokens
        if not t.is_whitespace
        and t.ttype not in (Comment, Comment.Single, Comment.Multiline)
    ]

    select_idx = -1
    from_idx = -1
    for i, t in enumerate(significant_tokens):
        if t.ttype is Keyword.DML and str(t.value).upper() == "SELECT":
            select_idx = i
        elif t.ttype is Keyword and str(t.value).upper() == "FROM":
            from_idx = i
            break

    if select_idx == -1 or from_idx == -1 or from_idx <= select_idx + 1:
        # Invalid query syntax (missing columns between SELECT and FROM or missing FROM)
        return False

    # Extract referenced tables
    tables = _extract_tables_from_tokens(statement.tokens)
    if not tables:
        return False

    # Verify all referenced tables belong to the allowed schema
    for tbl in tables:
        if tbl not in allowed_schema:
            return False

    return True


# -----------------------------------------------------------------------------
# Structured SQL Query Templates
# -----------------------------------------------------------------------------


class SQLQueryTemplate(BaseModel):
    """Structured parameterized SQL query template."""

    model_config = ConfigDict(frozen=True)

    query: str
    params: dict[str, Any] = Field(default_factory=dict)
    table: str = ""


def get_customer_template(
    customer_id: str | None = None,
    name: str | None = None,
    tier: str | None = None,
    industry: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for customers table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if customer_id is not None:
        conditions.append("id = :customer_id")
        params["customer_id"] = customer_id
    if name is not None:
        conditions.append("name = :name")
        params["name"] = name
    if tier is not None:
        conditions.append("tier = :tier")
        params["tier"] = tier
    if industry is not None:
        conditions.append("industry = :industry")
        params["industry"] = industry

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        f"SELECT id, name, tier, contract_value, industry FROM customers{where_clause}"
    )
    return SQLQueryTemplate(query=query, params=params, table="customers")


def get_incident_template(
    incident_id: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    service_id: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for incidents table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if incident_id is not None:
        conditions.append("id = :incident_id")
        params["incident_id"] = incident_id
    if severity is not None:
        conditions.append("severity = :severity")
        params["severity"] = severity
    if status is not None:
        conditions.append("status = :status")
        params["status"] = status
    if service_id is not None:
        conditions.append("impacted_service_id = :service_id")
        params["service_id"] = service_id

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        "SELECT id, title, severity, status, root_cause, impacted_service_id, occurred_at, resolved_at "
        f"FROM incidents{where_clause}"
    )
    return SQLQueryTemplate(query=query, params=params, table="incidents")


def get_service_template(
    service_id: str | None = None,
    name: str | None = None,
    tier: str | None = None,
    team_id: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for services table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if service_id is not None:
        conditions.append("id = :service_id")
        params["service_id"] = service_id
    if name is not None:
        conditions.append("name = :name")
        params["name"] = name
    if tier is not None:
        conditions.append("tier = :tier")
        params["tier"] = tier
    if team_id is not None:
        conditions.append("owner_team_id = :team_id")
        params["team_id"] = team_id

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT id, name, tier, port, repo_url, owner_team_id FROM services{where_clause}"
    return SQLQueryTemplate(query=query, params=params, table="services")


def get_team_template(
    team_id: str | None = None,
    name: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for teams table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if team_id is not None:
        conditions.append("id = :team_id")
        params["team_id"] = team_id
    if name is not None:
        conditions.append("name = :name")
        params["name"] = name

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        f"SELECT id, name, lead, slack_channel, description FROM teams{where_clause}"
    )
    return SQLQueryTemplate(query=query, params=params, table="teams")


def get_decision_template(
    decision_id: str | None = None,
    incident_id: str | None = None,
    status: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for decisions table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if decision_id is not None:
        conditions.append("id = :decision_id")
        params["decision_id"] = decision_id
    if incident_id is not None:
        conditions.append("incident_id = :incident_id")
        params["incident_id"] = incident_id
    if status is not None:
        conditions.append("status = :status")
        params["status"] = status

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        "SELECT id, title, status, context, decision, consequences, incident_id, decided_at "
        f"FROM decisions{where_clause}"
    )
    return SQLQueryTemplate(query=query, params=params, table="decisions")


def get_project_template(
    project_id: str | None = None,
    name: str | None = None,
    team_id: str | None = None,
    status: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for projects table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if project_id is not None:
        conditions.append("id = :project_id")
        params["project_id"] = project_id
    if name is not None:
        conditions.append("name = :name")
        params["name"] = name
    if team_id is not None:
        conditions.append("owner_team_id = :team_id")
        params["team_id"] = team_id
    if status is not None:
        conditions.append("status = :status")
        params["status"] = status

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT id, name, description, owner_team_id, status FROM projects{where_clause}"
    return SQLQueryTemplate(query=query, params=params, table="projects")


def get_ticket_template(
    ticket_id: str | None = None,
    project_id: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    assignee_id: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for tickets table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if ticket_id is not None:
        conditions.append("id = :ticket_id")
        params["ticket_id"] = ticket_id
    if project_id is not None:
        conditions.append("project_id = :project_id")
        params["project_id"] = project_id
    if priority is not None:
        conditions.append("priority = :priority")
        params["priority"] = priority
    if status is not None:
        conditions.append("status = :status")
        params["status"] = status
    if assignee_id is not None:
        conditions.append("assignee_id = :assignee_id")
        params["assignee_id"] = assignee_id

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT id, title, status, priority, project_id, assignee_id FROM tickets{where_clause}"
    return SQLQueryTemplate(query=query, params=params, table="tickets")


def get_employee_template(
    employee_id: str | None = None,
    email: str | None = None,
    team_id: str | None = None,
) -> SQLQueryTemplate:
    """Construct safe parameterized SQL query for employees table."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if employee_id is not None:
        conditions.append("id = :employee_id")
        params["employee_id"] = employee_id
    if email is not None:
        conditions.append("email = :email")
        params["email"] = email
    if team_id is not None:
        conditions.append("team_id = :team_id")
        params["team_id"] = team_id

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT id, name, email, role, team_id FROM employees{where_clause}"
    return SQLQueryTemplate(query=query, params=params, table="employees")


# -----------------------------------------------------------------------------
# Governed Execution and SQLRetriever
# -----------------------------------------------------------------------------


def _format_row_content(table: str, row_dict: dict[str, Any]) -> str:
    """Format row fields into concise structured key-value evidence text."""
    fields = [f"{k}={v}" for k, v in row_dict.items() if v is not None]
    return f"[{table}] " + " | ".join(fields)


def _execute_query_on_session(
    session: Session,
    sql_str: str,
    params: dict[str, Any] | None,
    sub_question_id: str,
    primary_table: str,
) -> list[Evidence]:
    """Execute validated statement on an active SQLAlchemy Session and map to Evidence."""
    result = session.execute(text(sql_str), params or {})
    rows = result.mappings().all()

    evidence_items: list[Evidence] = []
    for row in rows:
        row_dict = dict(row)
        row_id = (
            row_dict.get("id")
            or row_dict.get("customer_id")
            or row_dict.get("incident_id")
            or row_dict.get("service_id")
            or row_dict.get("team_id")
            or row_dict.get("ticket_id")
            or row_dict.get("project_id")
            or row_dict.get("employee_id")
        )

        content = _format_row_content(primary_table, row_dict)
        evidence = create_sql_evidence(
            sub_question_id=sub_question_id,
            table=primary_table,
            content=content,
            row_id=str(row_id) if row_id is not None else None,
            query=sql_str,
            score=1.0,
        )
        evidence_items.append(evidence)

    return evidence_items


def execute_governed_sql(
    sql_str: str,
    params: dict[str, Any] | None = None,
    db: Session | None = None,
    sub_question_id: str = "sq1",
    allowlist: set[str] | frozenset[str] | None = None,
) -> list[Evidence]:
    """Validate query with validate_sql and execute on a read-only database connection.

    Raises:
        SQLValidationError: If the statement violates AST validation or schema allowlists.

    Returns:
        list[Evidence]: Canonical Evidence items with source_type='sql' and locators.
    """
    if not validate_sql(sql_str, allowlist=allowlist):
        raise SQLValidationError(f"SQL statement failed validation: {sql_str}")

    parsed = sqlparse.parse(sql_str.strip())[0]
    primary_table = _detect_primary_table(parsed)

    if db is not None:
        return _execute_query_on_session(
            session=db,
            sql_str=sql_str,
            params=params,
            sub_question_id=sub_question_id,
            primary_table=primary_table,
        )

    # If no db session is injected, lazily open a short-lived session from global engine
    from backend.app.core.db import get_session_factory

    session_factory = get_session_factory()
    with session_factory() as session:
        return _execute_query_on_session(
            session=session,
            sql_str=sql_str,
            params=params,
            sub_question_id=sub_question_id,
            primary_table=primary_table,
        )


class SQLRetriever:
    """Governed SQL retrieval component for agent workflows (Claude.md §5)."""

    def __init__(
        self,
        db: Session | None = None,
        allowlist: set[str] | frozenset[str] | None = None,
    ) -> None:
        self.db = db
        self.allowlist = allowlist

    def retrieve(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        sub_question_id: str = "sq1",
    ) -> list[Evidence]:
        """Execute validated query string and return Evidence items."""
        return execute_governed_sql(
            sql_str=query,
            params=params,
            db=self.db,
            sub_question_id=sub_question_id,
            allowlist=self.allowlist,
        )

    def retrieve_from_template(
        self,
        template: SQLQueryTemplate,
        sub_question_id: str = "sq1",
    ) -> list[Evidence]:
        """Execute structured template and return Evidence items."""
        return execute_governed_sql(
            sql_str=template.query,
            params=template.params,
            db=self.db,
            sub_question_id=sub_question_id,
            allowlist=self.allowlist,
        )
