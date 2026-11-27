"""Unit tests for complexity classification and routing rules (P7-1, F3, F5, Claude.md §7.2, §18.4).

Validates:
- Complexity classification: simple, moderate, complex
- Single factual question -> simple -> exactly 1 sub-question, vector only, no SQL/Cypher
- Multi-domain join question -> complex -> <= 4 sub-questions (MAX_SUBQUESTIONS)
- Canonical question analysis, decomposition, and routing
- Routing floors overriding non-deterministic or incorrect LLM decisions
- Retrieval strategy signal detection: SQL, Graph, Hybrid, Vector
- Entity and fiscal time-range rule parsing
"""

from agents.rules import (
    MAX_SUBQUESTIONS,
    AnalysisResult,
    ComplexityResult,
    SubQuestion,
    analyze_query_rules,
    classify_complexity,
    decompose_query_rules,
    detect_retrieval_strategy,
    enforce_routing_floor,
)

CANONICAL_QUESTION = (
    "Which customers were impacted by the Payments API last quarter, what incidents occurred, "
    "which teams own those services, and what decisions were taken to prevent recurrence?"
)


def test_complexity_classification_simple_factual_query() -> None:
    """F3: Verify simple factual lookups are classified as 'simple' with 1 sub-question and vector only."""
    simple_queries = [
        "What is our corporate data retention policy for customer logs?",
        "What is the token TTL expiration for analyst sessions?",
        "What does ADR-042 recommend for connection pooling?",
    ]

    for query in simple_queries:
        res: ComplexityResult = classify_complexity(query)
        assert res.complexity == "simple"
        assert res.max_subquestions == 1
        assert res.rule_applied.startswith("RULE_SIMPLE")
        assert "vector" in res.allowed_strategies
        assert "sql" not in res.allowed_strategies
        assert "graph" not in res.allowed_strategies


def test_complexity_classification_moderate_query() -> None:
    """F3: Verify single-domain metrics or single-hop relationships classify as 'moderate'."""
    moderate_queries = [
        "How many SEV1 incidents occurred in the Payments API?",
        "Which team owns the Auth Service and Payments API?",
        "List all customers with active Enterprise tier status.",
    ]

    for query in moderate_queries:
        res: ComplexityResult = classify_complexity(query)
        assert res.complexity == "moderate"
        assert 1 <= res.max_subquestions <= 2
        assert res.rule_applied.startswith(
            "RULE_MODERATE"
        ) or res.rule_applied.startswith("RULE_SINGLE_DOMAIN")


def test_complexity_classification_complex_query() -> None:
    """F3: Verify cross-domain joins and canonical queries classify as 'complex'."""
    res: ComplexityResult = classify_complexity(CANONICAL_QUESTION)
    assert res.complexity == "complex"
    assert res.max_subquestions == MAX_SUBQUESTIONS
    assert res.max_subquestions == 4
    assert res.rule_applied in ("RULE_CANONICAL_QUERY", "RULE_CROSS_DOMAIN_JOIN")
    assert "vector" in res.allowed_strategies or "hybrid" in res.allowed_strategies
    assert "sql" in res.allowed_strategies
    assert "graph" in res.allowed_strategies


def test_canonical_question_analysis() -> None:
    """F2: Verify deterministic analysis extracts entities, fiscal dates, and required domains."""
    analysis: AnalysisResult = analyze_query_rules(CANONICAL_QUESTION)

    assert "Payments API" in analysis.entities or "payments-api" in [
        e.lower() for e in analysis.entities
    ]
    assert analysis.time_range is not None
    assert (
        "quarter" in analysis.time_range.lower()
        or "last quarter" in analysis.time_range.lower()
    )
    assert analysis.needs_graph is True, (
        "Must identify graph requirement for customers/teams"
    )
    assert analysis.needs_sql is True, (
        "Must identify SQL requirement for incident records"
    )
    assert analysis.needs_documents is True, (
        "Must identify document/hybrid requirement for decisions"
    )
    assert analysis.needs_aggregation is True or analysis.needs_relationships is True


def test_canonical_question_decomposition_and_routing() -> None:
    """F4, F5: Verify canonical query decomposes into exactly 4 sub-questions with correct routing."""
    sub_questions: list[SubQuestion] = decompose_query_rules(CANONICAL_QUESTION)

    assert len(sub_questions) == 4
    assert len(sub_questions) <= MAX_SUBQUESTIONS

    # Expected strategies for the 4 canonical sub-questions: graph, sql, graph, hybrid (Claude.md §415)
    strategies = [sq.strategy for sq in sub_questions]
    assert strategies == ["graph", "sql", "graph", "hybrid"]

    # Sub-question 1: Impacted customers
    assert "customer" in sub_questions[0].question.lower()
    assert sub_questions[0].strategy == "graph"

    # Sub-question 2: Incidents occurred during last quarter
    assert "incident" in sub_questions[1].question.lower()
    assert sub_questions[1].strategy == "sql"

    # Sub-question 3: Team service ownership
    assert (
        "team" in sub_questions[2].question.lower()
        or "own" in sub_questions[2].question.lower()
    )
    assert sub_questions[2].strategy == "graph"

    # Sub-question 4: Decisions to prevent recurrence
    assert (
        "decision" in sub_questions[3].question.lower()
        or "recurrence" in sub_questions[3].question.lower()
    )
    assert sub_questions[3].strategy == "hybrid"


def test_routing_floors_override_incorrect_llm_decisions() -> None:
    """Claude.md §7.2: Verify routing floors deterministically correct improper LLM retrieval choices."""
    # Scenario 1: LLM suggested vector for a relationship query
    sq_relationship = SubQuestion(
        id="sq1",
        question="Which engineering teams own the downstream services connected to Payments API?",
        strategy="vector",  # LLM mistakenly chose vector
    )
    corrected = enforce_routing_floor(sq_relationship, overall_complexity="complex")
    assert corrected.strategy == "graph"
    assert corrected.rule_applied == "RULE_FLOOR_RELATIONSHIP_REQUIRES_GRAPH"

    # Scenario 2: LLM suggested graph or vector for quantitative count/incident metrics
    sq_sql = SubQuestion(
        id="sq2",
        question="What incidents occurred on Payments API during last quarter with SEV1 status?",
        strategy="graph",  # LLM mistakenly chose graph
    )
    corrected_sql = enforce_routing_floor(sq_sql, overall_complexity="complex")
    assert corrected_sql.strategy == "sql"
    assert corrected_sql.rule_applied == "RULE_FLOOR_METRIC_REQUIRES_SQL"

    # Scenario 3: LLM suggested SQL for narrative architectural rationale
    sq_doc = SubQuestion(
        id="sq3",
        question="What decisions were taken to prevent recurrence of connection pool exhaustion?",
        strategy="sql",  # LLM mistakenly chose SQL
    )
    corrected_doc = enforce_routing_floor(sq_doc, overall_complexity="complex")
    assert corrected_doc.strategy == "hybrid"
    assert corrected_doc.rule_applied == "RULE_FLOOR_RATIONALE_REQUIRES_HYBRID"

    # Scenario 4: Simple query forbids SQL and Cypher
    sq_simple = SubQuestion(
        id="sq4",
        question="What is the data retention policy?",
        strategy="sql",  # LLM mistakenly chose SQL for simple query
    )
    corrected_simple = enforce_routing_floor(sq_simple, overall_complexity="simple")
    assert corrected_simple.strategy == "vector"
    assert corrected_simple.rule_applied == "RULE_FLOOR_SIMPLE_ONLY_VECTOR"


def test_detect_retrieval_strategy_signals() -> None:
    """F5: Verify keyword and semantic signal detectors assign appropriate store."""
    assert detect_retrieval_strategy("How many SEV1 incidents occurred in Q3?") == "sql"
    assert detect_retrieval_strategy("List all incidents with status resolved") == "sql"
    assert (
        detect_retrieval_strategy("Total count of customers in Enterprise tier")
        == "sql"
    )

    assert (
        detect_retrieval_strategy("Which teams own the Payments API service?")
        == "graph"
    )
    assert (
        detect_retrieval_strategy(
            "Show service dependencies and downstream impact of Redis"
        )
        == "graph"
    )
    assert (
        detect_retrieval_strategy("Which customers are impacted by incident INC-2031?")
        == "graph"
    )

    assert (
        detect_retrieval_strategy(
            "What ADR architectural decisions explain PgBouncer adoption?"
        )
        == "hybrid"
    )
    assert (
        detect_retrieval_strategy(
            "Explain the root cause and lessons learned from the outage postmortem"
        )
        == "hybrid"
    )
    assert (
        detect_retrieval_strategy("What policies govern disaster recovery procedures?")
        == "hybrid"
    )


def test_max_subquestions_ceiling() -> None:
    """F4: Verify decomposition never exceeds MAX_SUBQUESTIONS (4)."""
    long_verbose_query = (
        "Tell me everything about Payments API, Auth Service, and Checkout API, "
        "including all incidents, impacted customers, team owners, commit logs, "
        "SLAs, architectural decisions, postmortems, and compliance requirements."
    )
    sub_questions = decompose_query_rules(long_verbose_query)
    assert len(sub_questions) <= MAX_SUBQUESTIONS
    assert len(sub_questions) <= 4


def test_rule_models_validation() -> None:
    """Verify Pydantic models validate and serialize properly."""
    sub_q = SubQuestion(
        id="sq_test",
        question="Which teams own Payments API?",
        strategy="graph",
        target_entity="Payments API",
        rule_applied="RULE_GRAPH_OWNERSHIP",
    )
    assert sub_q.id == "sq_test"
    assert sub_q.strategy == "graph"

    data = sub_q.model_dump()
    rehydrated = SubQuestion.model_validate(data)
    assert rehydrated == sub_q
