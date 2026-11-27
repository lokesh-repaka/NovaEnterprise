"""Unit tests for Cypher query AST and security validator (P6-3, F8, F14, Claude.md §5, §8).

Validates the canonical security rules for validate_cypher():
1. Read-only MATCH ... RETURN queries pass
2. Parameterized MATCH queries pass
3. Multi-hop traversal MATCH queries pass
4. Destructive write statements (CREATE, DELETE, DETACH DELETE, SET, REMOVE, MERGE, DROP) are blocked
5. Semicolon chaining / multi-statement injection is blocked
6. Administrative / file load procedures (LOAD CSV, CALL dbms.*) are blocked
7. Empty, whitespace-only, comment-only, or invalid queries are blocked
"""

from rag.graph_retrieval import (
    CypherValidationError,
    validate_cypher,
)


class TestCypherValidator:
    """Unit tests proving validate_cypher() enforces read-only traversal security (F8, F14)."""

    def test_1_valid_simple_match(self) -> None:
        """Rule 1: Simple read-only MATCH query must succeed."""
        query = "MATCH (n:Service) RETURN n"
        assert validate_cypher(query) is True

    def test_2_valid_parameterized_match(self) -> None:
        """Rule 2: Parameterized read-only MATCH query must succeed."""
        query = "MATCH (i:Incident {id: $incident_id}) RETURN i"
        assert validate_cypher(query) is True

    def test_3_valid_multi_hop_traversal_match(self) -> None:
        """Rule 3: Multi-hop traversal query must succeed."""
        query = """
        MATCH (i:Incident {id: $incident_id})-[:AFFECTED]->(s:Service)-[:OWNED_BY]->(t:Team)
        MATCH (i)-[:IMPACTED]->(c:Customer)
        OPTIONAL MATCH (d:Decision)-[:ADDRESSED]->(i)
        RETURN i, s, t, c, d
        """
        assert validate_cypher(query) is True

    def test_4_destructive_writes_blocked(self) -> None:
        """Rule 4: Write clauses (CREATE, DELETE, SET, REMOVE, MERGE, DROP) must be blocked."""
        disallowed_queries = [
            "CREATE (n:Service {name: 'Malicious Service'})",
            "MATCH (n:Incident) DELETE n",
            "MATCH (n:Incident) DETACH DELETE n",
            "MATCH (c:Customer {id: 'cust-acme'}) SET c.tier = 'free'",
            "MATCH (s:Service {id: 'svc-payments-api'}) REMOVE s.tier",
            "MERGE (n:Team {name: 'Backdoor Team'})",
            "DROP INDEX ON :Service(name)",
            "DROP CONSTRAINT ON (n:Customer) ASSERT n.id IS UNIQUE",
        ]
        for query in disallowed_queries:
            assert validate_cypher(query) is False, f"Expected '{query}' to be blocked"

    def test_5_semicolon_chaining_blocked(self) -> None:
        """Rule 5: Multi-statement execution via semicolon chaining must be blocked."""
        chained_queries = [
            "MATCH (n:Service) RETURN n; MATCH (m:Team) DELETE m;",
            "MATCH (n:Service) RETURN n; CREATE (m:Hacked);",
            "MATCH (n:Incident) RETURN n; MATCH (c:Customer) RETURN c;",
        ]
        for query in chained_queries:
            assert validate_cypher(query) is False, (
                f"Expected chained query '{query}' to be blocked"
            )

    def test_6_dangerous_procedures_and_file_io_blocked(self) -> None:
        """Rule 6: External file load and dangerous database calls must be blocked."""
        dangerous_queries = [
            "LOAD CSV FROM 'file:///etc/passwd' AS line RETURN line",
            "CALL dbms.security.createUser('attacker', 'pwned', false)",
            "CALL apoc.periodic.iterate('MATCH (n) RETURN n', 'DELETE n', {batchSize:1000})",
            "CALL apoc.export.csv.all('export.csv', {})",
        ]
        for query in dangerous_queries:
            assert validate_cypher(query) is False, f"Expected '{query}' to be blocked"

    def test_7_empty_whitespace_and_invalid_syntax_blocked(self) -> None:
        """Rule 7: Empty, whitespace, comment-only, or invalid inputs must be blocked."""
        invalid_inputs = [
            "",
            "   ",
            "\n\t",
            "// just a cypher single-line comment",
            "/* cypher multiline comment */",
            "NOT A CYPHER QUERY AT ALL",
            "RETURN",
        ]
        for query in invalid_inputs:
            assert validate_cypher(query) is False, f"Expected '{query}' to be blocked"


def test_cypher_validation_error_raised() -> None:
    """Verify CypherValidationError inherits from Exception and formats message."""
    err = CypherValidationError("Malicious Cypher detected")
    assert isinstance(err, Exception)
    assert str(err) == "Malicious Cypher detected"
