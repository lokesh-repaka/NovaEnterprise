"""Unit tests for SQL AST validator (P6-2, F7, Claude.md §3.1).

Validates the 8 canonical security rules for validate_sql():
1. Read-only SELECT on allowlisted table succeeds
2. Multi-table JOIN on allowlisted tables succeeds
3. Semicolon injection / multi-statement execution is blocked
4. Destructive DDL statements (DROP, TRUNCATE, ALTER) are blocked
5. Destructive DML statements (DELETE, UPDATE, INSERT) are blocked
6. Non-allowlisted / sensitive tables (users, audit_logs, sqlite_master) are blocked
7. Dangerous system execution functions (load_extension, system, exec) are blocked
8. Empty, whitespace-only, or syntactically invalid queries are blocked
"""

from rag.sql_retrieval import (
    validate_sql,
)


class TestSQLValidator:
    """8 unit tests proving validate_sql() blocks injection and enforces schema allowlists (F7)."""

    def test_1_valid_select_on_allowlisted_table(self) -> None:
        """Rule 1: Simple read-only SELECT on an allowlisted table must pass."""
        query = "SELECT id, name, tier FROM customers WHERE tier = 'enterprise'"
        assert validate_sql(query) is True

    def test_2_valid_join_on_allowlisted_tables(self) -> None:
        """Rule 2: Complex SELECT with JOIN across allowlisted tables must pass."""
        query = """
        SELECT c.name, i.title, i.severity
        FROM customers c
        JOIN incidents i ON c.id = i.customer_id
        WHERE i.severity = 'SEV1'
        ORDER BY i.occurred_at DESC
        LIMIT 10
        """
        assert validate_sql(query) is True

    def test_3_semicolon_chaining_and_multi_statement_blocked(self) -> None:
        """Rule 3: Semicolon injection and multi-statement queries must be blocked."""
        # Chained DROP statement
        attack_1 = "SELECT * FROM customers; DROP TABLE incidents;"
        assert validate_sql(attack_1) is False

        # Chained SELECT statement
        attack_2 = "SELECT * FROM customers; SELECT * FROM services;"
        assert validate_sql(attack_2) is False

    def test_4_destructive_ddl_blocked(self) -> None:
        """Rule 4: DDL statements (DROP, TRUNCATE, ALTER, CREATE) must be blocked."""
        ddl_queries = [
            "DROP TABLE incidents",
            "TRUNCATE TABLE customers",
            "ALTER TABLE services ADD COLUMN hacked text",
            "CREATE TABLE backdoors (id int)",
        ]
        for query in ddl_queries:
            assert validate_sql(query) is False, f"Expected {query} to be rejected"

    def test_5_destructive_dml_blocked(self) -> None:
        """Rule 5: DML write statements (DELETE, UPDATE, INSERT) must be blocked."""
        dml_queries = [
            "DELETE FROM incidents WHERE id = 'inc-2031'",
            "UPDATE customers SET contract_value = 0 WHERE id = 'cust-acme'",
            "INSERT INTO services (id, name) VALUES ('svc-rogue', 'Rogue Service')",
        ]
        for query in dml_queries:
            assert validate_sql(query) is False, f"Expected {query} to be rejected"

    def test_6_non_allowlisted_and_system_tables_blocked(self) -> None:
        """Rule 6: Queries accessing tables outside ALLOWLISTED_TABLES must be blocked."""
        forbidden_queries = [
            "SELECT * FROM users",
            "SELECT * FROM audit_logs",
            "SELECT * FROM approval_requests",
            "SELECT * FROM sqlite_master",
            "SELECT * FROM information_schema.tables",
            "SELECT * FROM pg_catalog.pg_tables",
            "SELECT * FROM non_existent_financial_data",
        ]
        for query in forbidden_queries:
            assert validate_sql(query) is False, f"Expected {query} to be rejected"

    def test_7_dangerous_functions_and_commands_blocked(self) -> None:
        """Rule 7: System functions, shell execution, and comment bypasses must be blocked."""
        dangerous_queries = [
            "SELECT load_extension('evil.so') FROM customers",
            "SELECT readfile('/etc/passwd') FROM services",
            "SELECT * FROM customers WHERE id = '1' UNION SELECT username, password FROM users --",
            "EXEC xp_cmdshell('dir')",
            "SELECT sleep(10) FROM customers",
        ]
        for query in dangerous_queries:
            assert validate_sql(query) is False, f"Expected {query} to be rejected"

    def test_8_empty_whitespace_and_invalid_syntax_blocked(self) -> None:
        """Rule 8: Empty, whitespace, comment-only, or syntactically invalid queries must be blocked."""
        invalid_inputs = [
            "",
            "   ",
            "\n\t",
            "-- just a comment",
            "/* block comment */",
            "SELECT FROM WHERE",
            "NOT A SQL QUERY AT ALL",
        ]
        for query in invalid_inputs:
            assert validate_sql(query) is False, f"Expected '{query}' to be rejected"


def test_validate_sql_with_custom_allowlist() -> None:
    """Verify validate_sql accepts custom allowlist sets."""
    custom_allowlist = {"services"}
    assert validate_sql("SELECT * FROM services", allowlist=custom_allowlist) is True
    assert validate_sql("SELECT * FROM customers", allowlist=custom_allowlist) is False
