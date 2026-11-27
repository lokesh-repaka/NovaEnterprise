"""Unit tests for four-scope memory schemas and protocols (P8-1, F15, N1, Claude.md §7.4).

Validates:
- Four separated memory scopes: Working, Episodic, Semantic, Organizational (F15)
- Strong typing and Pydantic validation across all memory data models
- Secret scrubbing and prompt safety on memory entries (N8, N9)
- Organizational memory fiscal calendar resolution and service ownership lookups
- Protocol compliance (@runtime_checkable) for all scoped memory stores
- Full in-memory reference implementations with user and session isolation
"""

from datetime import timezone
from pathlib import Path

import pytest

from memory.protocols import (
    EpisodicMemoryStore,
    InMemoryEpisodicMemoryStore,
    InMemoryOrganizationalMemoryStore,
    InMemorySemanticMemoryStore,
    InMemoryUnifiedMemoryStore,
    InMemoryWorkingMemoryStore,
    OrganizationalMemoryStore,
    SemanticMemoryStore,
    UnifiedMemoryStore,
    WorkingMemoryStore,
)
from memory.schemas import (
    CompanyInfo,
    EpisodicMemoryEntry,
    FiscalCalendar,
    FiscalQuarter,
    FourScopeMemoryContext,
    MemoryItem,
    MemoryScope,
    OrganizationalMemory,
    SemanticMemoryEntry,
    ServiceTier,
    WorkingMemoryState,
)

# =====================================================================
# 1. Scope Enum & MemoryItem Generic Model Tests
# =====================================================================


def test_memory_scope_enum_values() -> None:
    """F15: Verify all four discrete memory scopes exist and match specification."""
    assert MemoryScope.WORKING == "working"
    assert MemoryScope.EPISODIC == "episodic"
    assert MemoryScope.SEMANTIC == "semantic"
    assert MemoryScope.ORGANIZATIONAL == "organizational"
    assert len(MemoryScope) == 4


def test_memory_item_creation_and_defaults() -> None:
    """Verify generic MemoryItem model fields, UUID default generation, and serialization."""
    item = MemoryItem(
        scope=MemoryScope.EPISODIC,
        key="recent_topic",
        content="Incident INC-2031 Payments API outage",
        session_id="sess_abc123",
        user_id="analyst@novaenterprise.io",
        metadata={"priority": "high"},
    )

    assert item.id.startswith("mem_")
    assert item.scope == MemoryScope.EPISODIC
    assert item.key == "recent_topic"
    assert item.content == "Incident INC-2031 Payments API outage"
    assert item.session_id == "sess_abc123"
    assert item.user_id == "analyst@novaenterprise.io"
    assert item.metadata["priority"] == "high"
    assert item.timestamp is not None
    assert item.timestamp.tzinfo == timezone.utc

    # Test serialization
    dump = item.model_dump()
    assert dump["scope"] == "episodic"
    restored = MemoryItem.model_validate(dump)
    assert restored.id == item.id
    assert restored.content == item.content


def test_memory_item_secret_scrubbing() -> None:
    """N8, N9: Verify secrets in memory item text content are automatically scrubbed."""
    fake_key = "sk_" + "live_" + "9876543210abcdef9876543210"
    item = MemoryItem(
        scope=MemoryScope.SEMANTIC,
        key="api_config_note",
        content=f"Connected using Stripe key {fake_key}",
        user_id="analyst@novaenterprise.io",
    )

    assert "sk_live_" not in str(item.content)
    assert "[REDACTED_API_KEY]" in str(item.content)


# =====================================================================
# 2. Scope-Specific Data Model Tests
# =====================================================================


def test_working_memory_state_operations() -> None:
    """Verify ephemeral in-run working memory state tracking and helper methods."""
    working = WorkingMemoryState(session_id="sess_run_01")

    assert working.session_id == "sess_run_01"
    assert working.current_sub_question_index == 0
    assert working.active_sub_question is None
    assert working.findings == []
    assert working.scratchpad == {}

    # State mutations
    working.set_active_sub_question(
        "Which customers were impacted by INC-2031?", index=1
    )
    assert working.active_sub_question == "Which customers were impacted by INC-2031?"
    assert working.current_sub_question_index == 1

    working.add_finding("Payments API experienced 42 minutes downtime.")
    working.add_finding("Acme Corp and Beta LLC reported transaction drops.")
    assert len(working.findings) == 2

    working.update_scratchpad("needs_graph_expansion", True)
    assert working.scratchpad["needs_graph_expansion"] is True

    working.clear_run_state()
    assert working.active_sub_question is None
    assert working.current_sub_question_index == 0
    assert working.findings == []
    assert working.scratchpad == {}


def test_episodic_memory_entry_and_secret_scrubbing() -> None:
    """Verify session-level conversation and interaction episodic memory tracking."""
    fake_aws_key = "AKIAIOSFODNN7EXAMPLE"
    entry = EpisodicMemoryEntry(
        session_id="sess_epi_01",
        turn_index=1,
        question=f"Check deployment logs for key {fake_aws_key}",
        answer="The deployment was initiated by PaymentService v2.4.",
        complexity="complex",
        citations=["doc:inc-2031#chunk-1", "sql:incidents#row-2031"],
        feedback="Helpful, verified by citations",
    )

    assert entry.id.startswith("epi_")
    assert entry.session_id == "sess_epi_01"
    assert entry.turn_index == 1
    assert fake_aws_key not in entry.question
    assert "[REDACTED_AWS_KEY]" in entry.question
    assert entry.complexity == "complex"
    assert len(entry.citations) == 2
    assert entry.feedback == "Helpful, verified by citations"
    assert entry.ttl_seconds == 86400  # Default 24h per PRD OQ-3


def test_semantic_memory_entry_operations() -> None:
    """Verify analyst-level persistent knowledge and preference memory tracking."""
    entry = SemanticMemoryEntry(
        user_id="analyst@novaenterprise.io",
        key="preferred_store_focus",
        content="Prioritize knowledge graph for customer dependency lookups",
        category="preference",
        confidence=0.95,
        metadata={"tags": ["graph", "customers"]},
    )

    assert entry.id.startswith("sem_")
    assert entry.user_id == "analyst@novaenterprise.io"
    assert entry.key == "preferred_store_focus"
    assert entry.category == "preference"
    assert entry.confidence == 0.95
    assert entry.metadata["tags"] == ["graph", "customers"]
    assert entry.created_at is not None
    assert entry.updated_at is not None


def test_organizational_memory_fiscal_calendar_resolution() -> None:
    """Verify enterprise constants, fiscal calendar parsing, and relative quarter resolution."""
    calendar = FiscalCalendar(
        fiscal_year=2026,
        fiscal_year_start="2026-01-01",
        fiscal_year_end="2026-12-31",
        current_quarter="2026-Q3",
        last_quarter="2026-Q2",
        quarters={
            "2026-Q1": FiscalQuarter(
                name="Fiscal Q1 2026",
                start_date="2026-01-01T00:00:00Z",
                end_date="2026-03-31T23:59:59Z",
                status="closed",
            ),
            "2026-Q2": FiscalQuarter(
                name="Fiscal Q2 2026",
                start_date="2026-04-01T00:00:00Z",
                end_date="2026-06-30T23:59:59Z",
                status="closed",
            ),
            "2026-Q3": FiscalQuarter(
                name="Fiscal Q3 2026",
                start_date="2026-07-01T00:00:00Z",
                end_date="2026-09-30T23:59:59Z",
                status="active",
            ),
            "2026-Q4": FiscalQuarter(
                name="Fiscal Q4 2026",
                start_date="2026-10-01T00:00:00Z",
                end_date="2026-12-31T23:59:59Z",
                status="future",
            ),
        },
    )

    # Direct resolution
    q2 = calendar.resolve_quarter("2026-Q2")
    assert q2 is not None
    assert q2.name == "Fiscal Q2 2026"
    assert q2.status == "closed"

    # Relative resolution
    last_q = calendar.resolve_quarter("last_quarter")
    assert last_q is not None
    assert last_q.name == "Fiscal Q2 2026"

    curr_q = calendar.resolve_quarter("current_quarter")
    assert curr_q is not None
    assert curr_q.status == "active"

    # Unknown quarter
    assert calendar.resolve_quarter("2025-Q1") is None


def test_organizational_memory_service_ownership_and_tiers() -> None:
    """Verify service ownership map and SLA service tier models."""
    org_mem = OrganizationalMemory(
        company_info=CompanyInfo(
            name="NovaEnterprise Inc.",
            domain="nova.io",
            headquarters="San Francisco, CA",
            default_currency="USD",
        ),
        fiscal_calendar=FiscalCalendar(
            fiscal_year=2026,
            fiscal_year_start="2026-01-01",
            fiscal_year_end="2026-12-31",
            current_quarter="2026-Q3",
            last_quarter="2026-Q2",
            quarters={},
        ),
        service_tiers={
            "tier-1": ServiceTier(
                description="Mission-critical customer-facing transactional services",
                availability_sla=0.9999,
                max_downtime_quarter_min=13.14,
                sev1_response_sla_min=15,
            )
        },
        service_ownership={
            "svc-payments-api": "team-payments",
            "svc-identity": "team-identity",
        },
    )

    assert org_mem.get_service_owner("svc-payments-api") == "team-payments"
    assert org_mem.get_service_owner("svc-unknown") is None

    tier1 = org_mem.get_service_tier("tier-1")
    assert tier1 is not None
    assert tier1.availability_sla == 0.9999
    assert tier1.sev1_response_sla_min == 15
    assert org_mem.get_service_tier("tier-99") is None


def test_organizational_memory_from_file_sample_data() -> None:
    """Verify loading organizational memory from sample_data/organizational_memory.json."""
    sample_path = Path("sample_data/organizational_memory.json")
    if not sample_path.exists():
        pytest.skip("sample_data/organizational_memory.json not found")

    org_mem = OrganizationalMemory.from_file(sample_path)
    assert org_mem.company_info.name == "NovaEnterprise Inc."
    assert org_mem.fiscal_calendar.current_quarter == "2026-Q3"
    assert "2026-Q2" in org_mem.fiscal_calendar.quarters
    assert org_mem.get_service_owner("svc-payments-api") == "team-payments"
    assert "tier-1" in org_mem.service_tiers


# =====================================================================
# 3. FourScopeMemoryContext Unified Snapshot Tests
# =====================================================================


def test_four_scope_memory_context_snapshot_and_prompt_formatting() -> None:
    """F15, N9: Verify FourScopeMemoryContext formats all 4 scopes cleanly for LLM prompts."""
    working = WorkingMemoryState(
        session_id="sess_unified_1",
        current_sub_question_index=1,
        active_sub_question="Which teams own Payments API?",
        findings=[
            "Payments API is owned by team-payments.",
            "Tier-1 availability SLA is 99.99%.",
        ],
    )

    episodic = [
        EpisodicMemoryEntry(
            session_id="sess_unified_1",
            turn_index=0,
            question="What was incident INC-2031?",
            answer="INC-2031 was a Payments API outage.",
            citations=["doc:inc-2031#chunk-1"],
        )
    ]

    semantic = [
        SemanticMemoryEntry(
            user_id="analyst@novaenterprise.io",
            key="focus_domain",
            content="Customer financial impact and SLA breaches",
            category="preference",
        )
    ]

    org = OrganizationalMemory(
        company_info=CompanyInfo(name="NovaEnterprise Inc."),
        fiscal_calendar=FiscalCalendar(
            fiscal_year=2026,
            current_quarter="2026-Q3",
            last_quarter="2026-Q2",
        ),
        service_ownership={"svc-payments-api": "team-payments"},
    )

    context = FourScopeMemoryContext(
        session_id="sess_unified_1",
        user_id="analyst@novaenterprise.io",
        working=working,
        episodic=episodic,
        semantic=semantic,
        organizational=org,
    )

    prompt_text = context.to_prompt_context()

    # Verify all four scopes are represented in the prompt context
    assert "### Working Memory" in prompt_text
    assert "Which teams own Payments API?" in prompt_text
    assert "Payments API is owned by team-payments." in prompt_text

    assert "### Episodic Memory (Session Context)" in prompt_text
    assert "What was incident INC-2031?" in prompt_text
    assert "INC-2031 was a Payments API outage." in prompt_text

    assert "### Semantic Memory (Analyst Profile)" in prompt_text
    assert "Customer financial impact and SLA breaches" in prompt_text

    assert "### Organizational Memory" in prompt_text
    assert "NovaEnterprise Inc." in prompt_text
    assert "Current Quarter: 2026-Q3" in prompt_text


# =====================================================================
# 4. Protocol Conformance & Store Implementation Tests
# =====================================================================


def test_protocol_runtime_checkable_conformance() -> None:
    """N3: Verify in-memory store classes satisfy respective Protocol interfaces."""
    working_store = InMemoryWorkingMemoryStore()
    assert isinstance(working_store, WorkingMemoryStore)

    episodic_store = InMemoryEpisodicMemoryStore()
    assert isinstance(episodic_store, EpisodicMemoryStore)

    semantic_store = InMemorySemanticMemoryStore()
    assert isinstance(semantic_store, SemanticMemoryStore)

    org_store = InMemoryOrganizationalMemoryStore()
    assert isinstance(org_store, OrganizationalMemoryStore)

    unified_store = InMemoryUnifiedMemoryStore(
        working=working_store,
        episodic=episodic_store,
        semantic=semantic_store,
        organizational=org_store,
    )
    assert isinstance(unified_store, UnifiedMemoryStore)


def test_working_memory_store_crud() -> None:
    """Verify working memory store get, save, and clear operations."""
    store = InMemoryWorkingMemoryStore()
    session_id = "sess_work_crud"

    assert store.get_state(session_id) is None

    state = WorkingMemoryState(session_id=session_id)
    state.add_finding("Found 3 customer records.")
    store.save_state(session_id, state)

    retrieved = store.get_state(session_id)
    assert retrieved is not None
    assert retrieved.session_id == session_id
    assert len(retrieved.findings) == 1

    store.clear_state(session_id)
    assert store.get_state(session_id) is None


def test_episodic_memory_store_turn_ordering_and_isolation() -> None:
    """Verify episodic memory store chronologically orders turns and isolates sessions."""
    store = InMemoryEpisodicMemoryStore()

    entry1 = EpisodicMemoryEntry(
        session_id="sess_A",
        turn_index=0,
        question="Question 1",
        answer="Answer 1",
    )
    entry2 = EpisodicMemoryEntry(
        session_id="sess_A",
        turn_index=1,
        question="Question 2",
        answer="Answer 2",
    )
    entry_b = EpisodicMemoryEntry(
        session_id="sess_B",
        turn_index=0,
        question="Session B Q",
        answer="Session B A",
    )

    store.add_entry(entry1)
    store.add_entry(entry2)
    store.add_entry(entry_b)

    # Session A entries in chronological turn order
    entries_a = store.get_entries("sess_A")
    assert len(entries_a) == 2
    assert entries_a[0].turn_index == 0
    assert entries_a[1].turn_index == 1

    # Session B isolated
    entries_b = store.get_entries("sess_B")
    assert len(entries_b) == 1
    assert entries_b[0].question == "Session B Q"

    # Limit check
    assert len(store.get_entries("sess_A", limit=1)) == 1

    # Clear session A
    store.clear_session("sess_A")
    assert len(store.get_entries("sess_A")) == 0
    assert len(store.get_entries("sess_B")) == 1


def test_semantic_memory_store_crud_and_user_isolation() -> None:
    """Verify semantic memory store CRUD, key lookup, category filtering, and user isolation."""
    store = InMemorySemanticMemoryStore()
    user_a = "analyst_a@nova.io"
    user_b = "analyst_b@nova.io"

    entry1 = SemanticMemoryEntry(
        user_id=user_a,
        key="strategy",
        content="Prefers graph first",
        category="preference",
    )
    entry2 = SemanticMemoryEntry(
        user_id=user_a,
        key="domain_knowledge",
        content="Payments API handles Stripe and Adyen webhooks",
        category="knowledge",
    )
    entry_b = SemanticMemoryEntry(
        user_id=user_b,
        key="strategy",
        content="Prefers vector RAG first",
        category="preference",
    )

    store.add_entry(entry1)
    store.add_entry(entry2)
    store.add_entry(entry_b)

    # Lookup by user
    all_a = store.get_entries(user_a)
    assert len(all_a) == 2

    # Filter by category
    pref_a = store.get_entries(user_a, category="preference")
    assert len(pref_a) == 1
    assert pref_a[0].content == "Prefers graph first"

    # Lookup by key
    key_entry = store.get_entry_by_key(user_a, "strategy")
    assert key_entry is not None
    assert key_entry.content == "Prefers graph first"

    # User B isolated
    key_b = store.get_entry_by_key(user_b, "strategy")
    assert key_b is not None
    assert key_b.content == "Prefers vector RAG first"

    # Delete entry
    deleted = store.delete_entry(user_a, entry1.id)
    assert deleted is True
    assert store.get_entry_by_key(user_a, "strategy") is None
    assert len(store.get_entries(user_a)) == 1

    # Clear user
    store.clear_user_memory(user_a)
    assert len(store.get_entries(user_a)) == 0
    assert len(store.get_entries(user_b)) == 1


def test_unified_memory_store_assembled_context() -> None:
    """Verify UnifiedMemoryStore coordinates across the 4 stores to yield a complete snapshot."""
    working_store = InMemoryWorkingMemoryStore()
    episodic_store = InMemoryEpisodicMemoryStore()
    semantic_store = InMemorySemanticMemoryStore()
    org_store = InMemoryOrganizationalMemoryStore()

    unified = InMemoryUnifiedMemoryStore(
        working=working_store,
        episodic=episodic_store,
        semantic=semantic_store,
        organizational=org_store,
    )

    session_id = "sess_coord_01"
    user_id = "analyst@nova.io"

    # Seed data
    working_state = WorkingMemoryState(session_id=session_id)
    working_state.add_finding("Finding A")
    working_store.save_state(session_id, working_state)

    episodic_store.add_entry(
        EpisodicMemoryEntry(
            session_id=session_id,
            turn_index=0,
            question="What is the fiscal year?",
            answer="Fiscal year is 2026.",
        )
    )

    semantic_store.add_entry(
        SemanticMemoryEntry(
            user_id=user_id,
            key="role",
            content="Senior Reliability Analyst",
        )
    )

    # Load context
    ctx = unified.assemble_context(session_id=session_id, user_id=user_id)
    assert ctx.session_id == session_id
    assert ctx.user_id == user_id
    assert len(ctx.working.findings) == 1
    assert len(ctx.episodic) == 1
    assert len(ctx.semantic) == 1
    assert ctx.organizational is not None
    assert ctx.organizational.company_info.name == "NovaEnterprise Inc."
