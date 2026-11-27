"""Deterministic complexity classification and routing rules (P7-1, F3, F5, Claude.md §7.2, §18.4).

Implements the non-negotiable rules-plus-LLM pattern:
- Deterministic analysis, decomposition, and routing rules applied on top of LLM output.
- Rules establish routing floors and policy constraints; the LLM adds judgment in grey areas only.
- Strict complexity-driven workflow shape:
    - simple: exactly 1 sub-question, no SQL, no Cypher, vector retrieval only.
    - moderate: 1–2 sub-questions, single-store or single-relationship focus.
    - complex: <= MAX_SUBQUESTIONS (default 4), cross-domain joins (SQL + Graph + Document).
- Hard ceiling: MAX_SUBQUESTIONS = 4.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

# Constants (Claude.md §3.1 F4, §7.3)
MAX_SUBQUESTIONS: int = 4

ComplexityLevel = Literal["simple", "moderate", "complex"]
RetrievalStrategy = Literal["vector", "sql", "graph", "hybrid"]

# Known enterprise ecosystem domain entities (Claude.md §2, §6, sample_data/)
KNOWN_SERVICES: tuple[str, ...] = (
    "Payments API",
    "Auth Service",
    "Core Banking",
    "Checkout API",
    "Notification Service",
    "User Service",
    "Order Service",
    "Inventory Service",
    "PgBouncer",
    "Redis",
    "PostgreSQL",
)

KNOWN_CUSTOMERS: tuple[str, ...] = (
    "Acme Corp",
    "Globex",
    "Soylent Corp",
    "Initech",
    "Umbrella Corp",
    "Wayne Enterprises",
    "Stark Industries",
    "Cyberdyne Systems",
)

KNOWN_TEAMS: tuple[str, ...] = (
    "Core Platform",
    "Payments Team",
    "Infra Core",
    "SRE",
    "Security",
    "Checkout Team",
    "Identity Team",
)

# Canonical question reference (Claude.md §30, docs/PRD.md §3)
CANONICAL_QUESTION_TEXT: str = (
    "Which customers were impacted by the Payments API last quarter, what incidents occurred, "
    "which teams own those services, and what decisions were taken to prevent recurrence?"
)


class ComplexityResult(BaseModel):
    """Result of deterministic complexity classification (F3)."""

    complexity: ComplexityLevel
    rule_applied: str
    max_subquestions: int
    allowed_strategies: list[RetrievalStrategy]
    rationale: str


class AnalysisResult(BaseModel):
    """Result of query intent, entity, and temporal extraction (F2)."""

    intent: str
    entities: list[str] = Field(default_factory=list)
    time_range: str | None = None
    needs_sql: bool = False
    needs_graph: bool = False
    needs_documents: bool = False
    needs_relationships: bool = False
    needs_aggregation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubQuestion(BaseModel):
    """A decomposed sub-question with assigned retrieval strategy (F4, F5)."""

    id: str
    question: str
    strategy: RetrievalStrategy
    target_entity: str | None = None
    rule_applied: str | None = None
    rationale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    """Audit record of a retrieval routing decision and floor enforcement."""

    sub_question_id: str
    original_strategy: RetrievalStrategy
    enforced_strategy: RetrievalStrategy
    rule_applied: str
    overridden: bool
    rationale: str


def _matches_any(text: str, patterns: list[str]) -> bool:
    """Case-insensitive pattern matcher."""
    text_lower = text.lower()
    return any(p.lower() in text_lower for p in patterns)


def analyze_query_rules(query: str) -> AnalysisResult:
    """Deterministically analyze a natural language question (F2).

    Extracts:
    - Domain entities (Services, Customers, Teams)
    - Fiscal or relative temporal ranges
    - Store requirement intent flags (SQL, Graph, Documents)
    """
    query_clean = query.strip()
    query_lower = query_clean.lower()

    # 1. Entity extraction
    extracted_entities: list[str] = []
    for svc in KNOWN_SERVICES:
        if re.search(rf"\b{re.escape(svc)}\b", query_clean, re.IGNORECASE):
            extracted_entities.append(svc)
    for cust in KNOWN_CUSTOMERS:
        if re.search(rf"\b{re.escape(cust)}\b", query_clean, re.IGNORECASE):
            extracted_entities.append(cust)
    for team in KNOWN_TEAMS:
        if re.search(rf"\b{re.escape(team)}\b", query_clean, re.IGNORECASE):
            extracted_entities.append(team)

    # 2. Temporal extraction
    time_range: str | None = None
    time_patterns = [
        (r"\blast quarter\b", "last quarter"),
        (r"\bthis quarter\b", "this quarter"),
        (r"\b(202[0-9]-q[1-4]|q[1-4]\s*202[0-9]|q[1-4])\b", None),
        (r"\bpast\s+(?:30|60|90)\s+days\b", None),
        (r"\byesterday\b", "yesterday"),
        (r"\blast\s+(?:week|month|year)\b", None),
    ]
    for pattern, fixed_val in time_patterns:
        match = re.search(pattern, query_lower)
        if match:
            time_range = fixed_val or match.group(0)
            break

    # 3. Store intent signal detection
    sql_signals = [
        "how many",
        "count",
        "number of",
        "incident",
        "incidents",
        "sev1",
        "sev2",
        "sev3",
        "status",
        "resolved",
        "outage duration",
        "metrics",
        "total",
        "quarter",
        "revenue",
        "sla",
    ]
    graph_signals = [
        "impacted by",
        "affected by",
        "who owns",
        "which team",
        "team own",
        "teams own",
        "ownership",
        "owned by",
        "dependencies",
        "depends on",
        "downstream",
        "upstream",
        "topology",
        "connected to",
        "customers were impacted",
        "customers are impacted",
        "impacted customers",
    ]
    doc_signals = [
        "decision",
        "decisions",
        "adr",
        "postmortem",
        "recurrence",
        "prevent recurrence",
        "why",
        "rationale",
        "root cause",
        "policy",
        "policies",
        "retention",
        "runbook",
        "lessons learned",
        "compliance",
    ]

    needs_sql = _matches_any(query_lower, sql_signals)
    needs_graph = _matches_any(query_lower, graph_signals)
    needs_documents = _matches_any(query_lower, doc_signals)
    needs_relationships = _matches_any(
        query_lower,
        ["own", "impact", "depend", "connect", "downstream"],
    )
    needs_aggregation = _matches_any(
        query_lower,
        ["count", "how many", "total", "average", "sum", "number of"],
    )

    intent = (
        "cross_domain_research"
        if (needs_sql and needs_graph and needs_documents)
        else "factual_query"
    )

    return AnalysisResult(
        intent=intent,
        entities=extracted_entities,
        time_range=time_range,
        needs_sql=needs_sql,
        needs_graph=needs_graph,
        needs_documents=needs_documents,
        needs_relationships=needs_relationships,
        needs_aggregation=needs_aggregation,
    )


def classify_complexity(
    query: str,
    analysis: AnalysisResult | None = None,
) -> ComplexityResult:
    """Classify query complexity as simple, moderate, or complex (F3).

    Rules:
    - Canonical 4-way question or queries combining >= 3 domain facets (SQL + Graph + Document)
      classify as 'complex' (RULE_CANONICAL_QUERY or RULE_CROSS_DOMAIN_JOIN).
    - Queries asking for single-domain metrics or single-hop relationships
      classify as 'moderate' (RULE_SINGLE_DOMAIN_METRIC / RULE_SINGLE_DOMAIN_RELATIONSHIP).
    - Single factual, policy, definition, or runbook lookups
      classify as 'simple' (RULE_SIMPLE_FACTUAL).
    """
    if analysis is None:
        analysis = analyze_query_rules(query)

    query_lower = query.lower()

    # Check for canonical question pattern
    is_canonical = (
        "payments api" in query_lower
        and "customer" in query_lower
        and "incident" in query_lower
        and (
            "decision" in query_lower
            or "recurrence" in query_lower
            or "prevent" in query_lower
        )
    )
    if is_canonical:
        return ComplexityResult(
            complexity="complex",
            rule_applied="RULE_CANONICAL_QUERY",
            max_subquestions=MAX_SUBQUESTIONS,
            allowed_strategies=["graph", "sql", "hybrid", "vector"],
            rationale="Canonical cross-domain question spanning customers, incidents, teams, and decisions.",
        )

    # Check for multi-domain cross-store joins
    domain_facets = 0
    if analysis.needs_sql:
        domain_facets += 1
    if analysis.needs_graph:
        domain_facets += 1
    if analysis.needs_documents:
        domain_facets += 1

    if domain_facets >= 2 and (analysis.needs_sql and analysis.needs_graph):
        return ComplexityResult(
            complexity="complex",
            rule_applied="RULE_CROSS_DOMAIN_JOIN",
            max_subquestions=MAX_SUBQUESTIONS,
            allowed_strategies=["graph", "sql", "hybrid", "vector"],
            rationale="Query requires joining relational records and graph topology across multiple stores.",
        )

    if domain_facets >= 3:
        return ComplexityResult(
            complexity="complex",
            rule_applied="RULE_CROSS_DOMAIN_JOIN",
            max_subquestions=MAX_SUBQUESTIONS,
            allowed_strategies=["graph", "sql", "hybrid", "vector"],
            rationale="Query spans SQL, graph relationships, and document rationale.",
        )

    # Check for single-domain relationship or single SQL store query (moderate)
    # (Claude.md §285: simple forbids SQL and Cypher, so SQL/graph requirements are at least moderate)
    if analysis.needs_graph:
        return ComplexityResult(
            complexity="moderate",
            rule_applied="RULE_SINGLE_DOMAIN_RELATIONSHIP",
            max_subquestions=2,
            allowed_strategies=["graph", "vector"],
            rationale="Query investigates entity relationships or ownership topology in graph store.",
        )

    if analysis.needs_sql:
        return ComplexityResult(
            complexity="moderate",
            rule_applied="RULE_SINGLE_DOMAIN_METRIC",
            max_subquestions=2,
            allowed_strategies=["sql", "vector"],
            rationale="Query computes counts, aggregations, or filtered record metrics in SQL store.",
        )

    # Check for multi-entity comparison
    if len(analysis.entities) >= 2:
        return ComplexityResult(
            complexity="moderate",
            rule_applied="RULE_MODERATE_MULTI_ENTITY",
            max_subquestions=2,
            allowed_strategies=["graph", "vector"],
            rationale="Query compares or queries across two distinct entities.",
        )

    # Default to simple factual lookup (Claude.md §285: exactly 1 sub-question, vector only)
    return ComplexityResult(
        complexity="simple",
        rule_applied="RULE_SIMPLE_FACTUAL",
        max_subquestions=1,
        allowed_strategies=["vector"],
        rationale="Simple factual inquiry satisfiable via single vector document search.",
    )


def detect_retrieval_strategy(sub_question_text: str) -> RetrievalStrategy:
    """Detect the most appropriate retrieval strategy for a sub-question (F5).

    Signals:
    - Counts, metrics, status, dates, incident lists -> 'sql'
    - Topology, team ownership, downstream dependencies, impacted customers -> 'graph'
    - ADRs, postmortems, decisions, root causes, policies, runbooks -> 'hybrid'
    - Fallback -> 'vector'
    """
    text = sub_question_text.lower()

    # 1. SQL metrics, counts, and tabular criteria
    sql_keywords = [
        "how many",
        "count of",
        "number of",
        "total count",
        "incidents occurred",
        "incident count",
        "sev1",
        "sev2",
        "status resolved",
        "status active",
        "outage duration",
        "date between",
        "last quarter",
        "in q",
    ]
    if _matches_any(text, sql_keywords):
        return "sql"

    # Explicit SQL incident listing check
    if re.search(r"\b(what|which|list)\s+incidents?\b", text) and (
        "quarter" in text or "occurred" in text or "status" in text or "sev" in text
    ):
        return "sql"

    # 2. Graph topology, team ownership, dependencies, and impacted customers
    graph_keywords = [
        "which team",
        "which teams",
        "who owns",
        "team own",
        "teams own",
        "team ownership",
        "service ownership",
        "impacted by",
        "customers were impacted",
        "customers are impacted",
        "impacted customers",
        "downstream dependencies",
        "service dependencies",
        "depends on",
        "topology",
        "affected by",
    ]
    if _matches_any(text, graph_keywords):
        return "graph"

    # 3. Hybrid document retrieval for technical rationale, postmortems, ADRs
    hybrid_keywords = [
        "decision",
        "decisions",
        "adr",
        "postmortem",
        "prevent recurrence",
        "recurrence",
        "root cause",
        "why",
        "rationale",
        "lessons learned",
        "policy",
        "policies",
        "retention",
        "runbook",
        "disaster recovery",
    ]
    if _matches_any(text, hybrid_keywords):
        return "hybrid"

    # 4. Default to vector
    return "vector"


def enforce_routing_floor(
    sub_question: SubQuestion,
    overall_complexity: ComplexityLevel = "complex",
) -> SubQuestion:
    """Enforce deterministic routing floors on top of LLM strategy choices (Claude.md §7.2, §18.4).

    Guarantees:
    - If overall_complexity is 'simple', strategy MUST be 'vector' (blocks SQL and Cypher).
    - If sub-question asks for relationship / ownership / topology, strategy MUST be 'graph'.
    - If sub-question asks for counts, dates, incidents table status, strategy MUST be 'sql'.
    - If sub-question asks for ADR, postmortem, or root cause rationale, strategy MUST be 'hybrid'.
    """
    text = sub_question.question.lower()
    current_strategy = sub_question.strategy

    # 1. Floor for simple queries (Claude.md §285: simple -> vector only, no SQL, no Cypher)
    if overall_complexity == "simple":
        if current_strategy != "vector":
            return SubQuestion(
                id=sub_question.id,
                question=sub_question.question,
                strategy="vector",
                target_entity=sub_question.target_entity,
                rule_applied="RULE_FLOOR_SIMPLE_ONLY_VECTOR",
                rationale="Simple complexity inquiries are restricted to vector retrieval only.",
                metadata=sub_question.metadata,
            )
        return sub_question

    # 2. Floor for relationship, ownership, and topology queries -> graph
    graph_signals = [
        "which team",
        "which teams",
        "who owns",
        "team own",
        "teams own",
        "ownership",
        "impacted by",
        "customers were impacted",
        "customers are impacted",
        "impacted customers",
        "downstream",
        "dependencies",
        "depends on",
    ]
    if _matches_any(text, graph_signals):
        if current_strategy != "graph":
            return SubQuestion(
                id=sub_question.id,
                question=sub_question.question,
                strategy="graph",
                target_entity=sub_question.target_entity,
                rule_applied="RULE_FLOOR_RELATIONSHIP_REQUIRES_GRAPH",
                rationale="Relationship and topology queries must route to graph store.",
                metadata=sub_question.metadata,
            )
        return sub_question

    # 3. Floor for quantitative metrics, counts, and incident records -> sql
    sql_signals = [
        "how many",
        "count of",
        "number of",
        "total count",
        "incidents occurred",
        "sev1",
        "sev2",
        "status resolved",
        "outage duration",
        "date between",
        "what incidents occurred",
    ]
    if _matches_any(text, sql_signals):
        if current_strategy != "sql":
            return SubQuestion(
                id=sub_question.id,
                question=sub_question.question,
                strategy="sql",
                target_entity=sub_question.target_entity,
                rule_applied="RULE_FLOOR_METRIC_REQUIRES_SQL",
                rationale="Quantitative count and tabular record inquiries must route to SQL store.",
                metadata=sub_question.metadata,
            )
        return sub_question

    # 4. Floor for technical decisions, ADRs, postmortems -> hybrid
    doc_signals = [
        "decision",
        "decisions",
        "adr",
        "postmortem",
        "prevent recurrence",
        "root cause",
        "why",
        "rationale",
        "lessons learned",
    ]
    if _matches_any(text, doc_signals):
        if current_strategy not in ("hybrid", "vector"):
            return SubQuestion(
                id=sub_question.id,
                question=sub_question.question,
                strategy="hybrid",
                target_entity=sub_question.target_entity,
                rule_applied="RULE_FLOOR_RATIONALE_REQUIRES_HYBRID",
                rationale="Technical rationale and decision inquiries must route to hybrid document retriever.",
                metadata=sub_question.metadata,
            )
        return sub_question

    # No override needed
    return sub_question


def decompose_query_rules(
    query: str,
    analysis: AnalysisResult | None = None,
) -> list[SubQuestion]:
    """Decompose a question into focused sub-questions with assigned retrieval strategies (F4, F5).

    Guarantees:
    - Never exceeds MAX_SUBQUESTIONS (4).
    - Canonical question produces the deterministic 4 sub-questions in exact order:
      1. graph: impacted customers
      2. sql: incidents during last quarter
      3. graph: team service ownership
      4. hybrid: decisions to prevent recurrence
      (Claude.md §415: graph, sql, graph, hybrid)
    - Simple queries produce exactly 1 sub-question with strategy 'vector'.
    """
    if analysis is None:
        analysis = analyze_query_rules(query)

    query_lower = query.lower()

    # Canonical question check
    is_canonical = (
        "payments api" in query_lower
        and "customer" in query_lower
        and "incident" in query_lower
        and (
            "decision" in query_lower
            or "recurrence" in query_lower
            or "prevent" in query_lower
        )
    )

    if is_canonical:
        return [
            SubQuestion(
                id="sq1",
                question="Which customers were impacted by incidents on the Payments API?",
                strategy="graph",
                target_entity="Payments API",
                rule_applied="RULE_CANONICAL_DECOMP_GRAPH_CUSTOMERS",
                rationale="Traverse graph relationships from Payments API through Incidents to Impacted Customers.",
            ),
            SubQuestion(
                id="sq2",
                question="What incidents occurred on the Payments API during last quarter?",
                strategy="sql",
                target_entity="Payments API",
                rule_applied="RULE_CANONICAL_DECOMP_SQL_INCIDENTS",
                rationale="Query relational incidents table with service and fiscal quarter date range filtering.",
            ),
            SubQuestion(
                id="sq3",
                question="Which teams own the services related to Payments API?",
                strategy="graph",
                target_entity="Payments API",
                rule_applied="RULE_CANONICAL_DECOMP_GRAPH_TEAMS",
                rationale="Traverse graph ownership edges from Payments API and dependencies to owning teams.",
            ),
            SubQuestion(
                id="sq4",
                question="What decisions and postmortems were documented to prevent recurrence of Payments API outages?",
                strategy="hybrid",
                target_entity="Payments API",
                rule_applied="RULE_CANONICAL_DECOMP_HYBRID_DECISIONS",
                rationale="Execute hybrid RRF search over postmortem root causes and ADRs (e.g. ADR-042 PgBouncer).",
            ),
        ]

    # Complexity classification
    complexity_res = classify_complexity(query, analysis)

    # Simple query -> exactly 1 sub-question (Claude.md §285)
    if complexity_res.complexity == "simple":
        target = analysis.entities[0] if analysis.entities else None
        return [
            SubQuestion(
                id="sq1",
                question=query.strip(),
                strategy="vector",
                target_entity=target,
                rule_applied=complexity_res.rule_applied,
                rationale="Single sub-question for simple factual query routed to vector retrieval.",
            )
        ]

    # Moderate or multi-store query
    sub_questions: list[SubQuestion] = []
    target = analysis.entities[0] if analysis.entities else "System"

    if analysis.needs_graph:
        sub_questions.append(
            SubQuestion(
                id=f"sq{len(sub_questions) + 1}",
                question=f"What are the ownership and relationship dependencies for {target}?",
                strategy="graph",
                target_entity=target,
                rule_applied="RULE_DECOMP_GRAPH",
                rationale="Graph traversal for entity relationships.",
            )
        )

    if analysis.needs_sql and len(sub_questions) < MAX_SUBQUESTIONS:
        time_part = f" for {analysis.time_range}" if analysis.time_range else ""
        sub_questions.append(
            SubQuestion(
                id=f"sq{len(sub_questions) + 1}",
                question=f"What are the incident records and status metrics for {target}{time_part}?",
                strategy="sql",
                target_entity=target,
                rule_applied="RULE_DECOMP_SQL",
                rationale="Relational query for metrics and records.",
            )
        )

    if analysis.needs_documents and len(sub_questions) < MAX_SUBQUESTIONS:
        sub_questions.append(
            SubQuestion(
                id=f"sq{len(sub_questions) + 1}",
                question=f"What architectural decisions and documentation apply to {target}?",
                strategy="hybrid",
                target_entity=target,
                rule_applied="RULE_DECOMP_HYBRID",
                rationale="Hybrid document retrieval for rationale.",
            )
        )

    # Fallback if no specific facet was generated
    if not sub_questions:
        strategy = detect_retrieval_strategy(query)
        sub_questions.append(
            SubQuestion(
                id="sq1",
                question=query.strip(),
                strategy=strategy,
                target_entity=target,
                rule_applied="RULE_DECOMP_DEFAULT",
                rationale=f"Default decomposition routed to {strategy}.",
            )
        )

    # Enforce MAX_SUBQUESTIONS hard ceiling
    return sub_questions[:MAX_SUBQUESTIONS]
