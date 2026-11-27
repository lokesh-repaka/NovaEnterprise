"""Unit tests for Unified Memory Recall and Update Service (P8-3, F15, N1, Claude.md §7.4).

Validates:
- MemoryService coordinating all four memory scopes (Working, Episodic, Semantic, Organizational)
- Unified snapshot recall via FourScopeMemoryContext and prompt context formatting
- Episodic multi-turn interaction recording with auto-incrementing turn indices
- Working state mutations (active sub-question, accumulated findings, scratchpad)
- Semantic memory analyst CRUD and strict user isolation
- Organizational memory queries (fiscal calendar, quarters, service ownership, SLA tiers)
- Complete session memory cleanup
- Fail-safe resilience on degraded backends
- Global singleton lifecycle
"""

from unittest.mock import MagicMock

from memory.memory_service import (
    MemoryService,
    get_memory_service,
    reset_memory_service,
)
from memory.protocols import (
    InMemoryEpisodicMemoryStore,
    InMemoryOrganizationalMemoryStore,
    InMemorySemanticMemoryStore,
    InMemoryWorkingMemoryStore,
    UnifiedMemoryStore,
)
from memory.schemas import (
    FourScopeMemoryContext,
    OrganizationalMemory,
    WorkingMemoryState,
)


def test_memory_service_initialization_defaults() -> None:
    """F15, N3: Verify MemoryService initializes with all four memory scope stores."""
    service = MemoryService()
    assert service.working is not None
    assert service.episodic is not None
    assert service.semantic is not None
    assert service.organizational is not None
    assert isinstance(service, UnifiedMemoryStore)


def test_recall_context_assembled_snapshot() -> None:
    """F15: Verify recall() compiles a FourScopeMemoryContext snapshot across all 4 tiers."""
    working_store = InMemoryWorkingMemoryStore()
    episodic_store = InMemoryEpisodicMemoryStore()
    semantic_store = InMemorySemanticMemoryStore()
    org_store = InMemoryOrganizationalMemoryStore()

    service = MemoryService(
        working_store=working_store,
        episodic_store=episodic_store,
        semantic_store=semantic_store,
        org_store=org_store,
    )

    session_id = "sess_recall_snap"
    user_id = "analyst@novaenterprise.io"

    # Seed working state
    service.update_working_state(
        session_id=session_id,
        active_sub_question="Which teams own Payments API?",
        sub_question_index=0,
        finding="Payments API is Tier-1 owned by team-payments.",
    )

    # Seed episodic interaction
    service.update_turn(
        session_id=session_id,
        question="What happened in INC-2031?",
        answer="INC-2031 was a 42-minute outage in Payments API.",
        citations=["doc:inc-2031#chunk-1"],
        complexity="complex",
        user_id=user_id,
    )

    # Seed semantic profile
    service.save_semantic_insight(
        user_id=user_id,
        key="focus_domain",
        content="Incident postmortems and customer SLA impacts",
        category="preference",
    )

    # Recall full snapshot
    context: FourScopeMemoryContext = service.recall(
        session_id=session_id, user_id=user_id
    )
    assert isinstance(context, FourScopeMemoryContext)
    assert context.session_id == session_id
    assert context.user_id == user_id

    # Working scope verified
    assert context.working.active_sub_question == "Which teams own Payments API?"
    assert len(context.working.findings) == 1

    # Episodic scope verified
    assert len(context.episodic) == 1
    assert context.episodic[0].question == "What happened in INC-2031?"
    assert context.episodic[0].turn_index == 0

    # Semantic scope verified
    assert len(context.semantic) == 1
    assert context.semantic[0].key == "focus_domain"

    # Organizational scope verified
    assert context.organizational is not None
    assert context.organizational.company_info.name == "NovaEnterprise Inc."

    # Prompt text formatting verified
    prompt_text = service.recall_prompt_context(session_id=session_id, user_id=user_id)
    assert "### Working Memory" in prompt_text
    assert "Which teams own Payments API?" in prompt_text
    assert "### Episodic Memory" in prompt_text
    assert "INC-2031 was a 42-minute outage" in prompt_text
    assert "### Semantic Memory" in prompt_text
    assert "### Organizational Memory" in prompt_text


def test_update_turn_and_episodic_auto_increment() -> None:
    """Verify update_turn automatically computes next turn index and scrubs secrets."""
    service = MemoryService()
    session_id = "sess_turn_seq"
    service.clear_session_memory(session_id)

    # Turn 0
    t0 = service.update_turn(
        session_id=session_id,
        question="Question zero",
        answer="Answer zero",
    )
    assert t0.turn_index == 0

    # Turn 1 with secret in question
    fake_api_key = "sk_" + "live_" + "1234567890abcdef1234567890"
    t1 = service.update_turn(
        session_id=session_id,
        question=f"Question one with key {fake_api_key}",
        answer="Answer one",
        citations=["doc:api#chunk-2"],
        complexity="simple",
    )
    assert t1.turn_index == 1
    assert "sk_live_" not in t1.question
    assert "[REDACTED_API_KEY]" in t1.question

    # Turn 2
    t2 = service.update_turn(
        session_id=session_id,
        question="Question two",
        answer="Answer two",
    )
    assert t2.turn_index == 2

    # Verify history
    history = service.get_episodic_history(session_id)
    assert len(history) == 3
    assert [turn.turn_index for turn in history] == [0, 1, 2]

    # Verify limit capping
    recent = service.get_episodic_history(session_id, limit=2)
    assert len(recent) == 2
    assert [turn.turn_index for turn in recent] == [1, 2]

    service.clear_session_memory(session_id)


def test_update_working_state_mutations() -> None:
    """Verify working state incremental updates, findings accumulation, and scratchpad flags."""
    service = MemoryService()
    session_id = "sess_work_mut"
    service.clear_session_memory(session_id)

    state1 = service.update_working_state(
        session_id=session_id,
        active_sub_question="Check service dependencies",
        sub_question_index=0,
        finding="Finding 1: Payments API calls Database.",
        scratchpad_update={"checked_db": True},
        last_node="analyze_query",
    )

    assert state1.active_sub_question == "Check service dependencies"
    assert state1.current_sub_question_index == 0
    assert len(state1.findings) == 1
    assert state1.scratchpad["checked_db"] is True
    assert state1.last_node == "analyze_query"

    # Second mutation adds finding without replacing existing
    state2 = service.update_working_state(
        session_id=session_id,
        active_sub_question="Check customer impact",
        sub_question_index=1,
        finding="Finding 2: 4 tier-1 customers impacted.",
        scratchpad_update={"checked_customers": True},
        last_node="retrieve_graph",
    )

    assert state2.active_sub_question == "Check customer impact"
    assert state2.current_sub_question_index == 1
    assert len(state2.findings) == 2
    assert state2.scratchpad["checked_db"] is True
    assert state2.scratchpad["checked_customers"] is True
    assert state2.last_node == "retrieve_graph"

    # Query helper directly
    queried = service.get_working_state(session_id)
    assert queried.current_sub_question_index == 1
    assert len(queried.findings) == 2

    service.clear_session_memory(session_id)


def test_semantic_knowledge_crud_and_user_isolation() -> None:
    """Verify analyst semantic memory CRUD, key lookups, and analyst boundary isolation."""
    service = MemoryService()
    user_a = "analyst_a@nova.io"
    user_b = "analyst_b@nova.io"

    service.clear_user_semantic_memory(user_a)
    service.clear_user_semantic_memory(user_b)

    # User A records preferences and domain knowledge
    entry_a1 = service.save_semantic_insight(
        user_id=user_a,
        key="query_preference",
        content="Prefers graph-first traversal for multi-hop questions",
        category="preference",
    )
    service.save_semantic_insight(
        user_id=user_a,
        key="domain_term",
        content="Payments API internal codename is Project Volt",
        category="glossary",
    )

    # User B records different preference
    service.save_semantic_insight(
        user_id=user_b,
        key="query_preference",
        content="Prefers vector search first",
        category="preference",
    )

    # Verify User A entries
    all_a = service.get_semantic_knowledge(user_a)
    assert len(all_a) == 2

    prefs_a = service.get_semantic_knowledge(user_a, category="preference")
    assert len(prefs_a) == 1
    assert prefs_a[0].content == "Prefers graph-first traversal for multi-hop questions"

    # Verify User B isolation
    all_b = service.get_semantic_knowledge(user_b)
    assert len(all_b) == 1
    assert all_b[0].content == "Prefers vector search first"

    # Delete entry for User A
    deleted = service.delete_semantic_insight(user_a, entry_a1.id)
    assert deleted is True
    assert len(service.get_semantic_knowledge(user_a)) == 1

    # Cleanup
    service.clear_user_semantic_memory(user_a)
    service.clear_user_semantic_memory(user_b)
    assert len(service.get_semantic_knowledge(user_a)) == 0
    assert len(service.get_semantic_knowledge(user_b)) == 0


def test_organizational_memory_helpers() -> None:
    """Verify service delegation to organizational memory store."""
    service = MemoryService()

    # Quarter resolution
    last_q = service.resolve_quarter("last_quarter")
    assert last_q is not None
    assert last_q.name == "Fiscal Q2 2026"

    curr_q = service.resolve_quarter("2026-Q3")
    assert curr_q is not None
    assert curr_q.status == "active"

    # Service ownership
    assert service.get_service_owner("svc-payments-api") == "team-payments"
    assert service.get_service_owner("svc-identity") == "team-identity"
    assert service.get_service_owner("svc-nonexistent") is None

    # Service tier
    tier1 = service.get_service_tier("tier-1")
    assert tier1 is not None
    assert tier1.availability_sla == 0.9999

    tier_none = service.get_service_tier("tier-none")
    assert tier_none is None

    # Full model
    org = service.get_organizational_memory()
    assert isinstance(org, OrganizationalMemory)
    assert org.company_info.name == "NovaEnterprise Inc."


def test_clear_session_memory_clears_working_and_episodic() -> None:
    """Verify clear_session_memory purges working memory state and episodic Redis records."""
    service = MemoryService()
    session_id = "sess_purge_test"

    service.update_working_state(session_id, finding="Ephemeral finding")
    service.update_turn(session_id, question="Q?", answer="A.")

    assert len(service.get_working_state(session_id).findings) == 1
    assert len(service.get_episodic_history(session_id)) == 1

    service.clear_session_memory(session_id)

    assert service.get_working_state(session_id).findings == []
    assert len(service.get_episodic_history(session_id)) == 0


def test_resilience_and_fail_safe_operations() -> None:
    """Claude.md §7.3, §16: Memory operations must never raise or crash workflows on store failures."""
    broken_working = MagicMock()
    broken_working.get_state.side_effect = RuntimeError("Working store failure")
    broken_working.save_state.side_effect = RuntimeError("Working store failure")

    broken_episodic = MagicMock()
    broken_episodic.add_entry.side_effect = RuntimeError("Episodic store failure")
    broken_episodic.get_entries.side_effect = RuntimeError("Episodic store failure")

    broken_semantic = MagicMock()
    broken_semantic.get_entries.side_effect = RuntimeError("Semantic store failure")

    broken_org = MagicMock()
    broken_org.load.side_effect = RuntimeError("Org store failure")

    resilient_service = MemoryService(
        working_store=broken_working,
        episodic_store=broken_episodic,
        semantic_store=broken_semantic,
        org_store=broken_org,
    )

    # 1. Recall must not raise
    ctx = resilient_service.recall("sess_broken", "user_broken")
    assert isinstance(ctx, FourScopeMemoryContext)
    assert ctx.session_id == "sess_broken"

    # 2. Update turn must not raise
    turn = resilient_service.update_turn("sess_broken", "Q", "A")
    assert turn is not None
    assert turn.question == "Q"

    # 3. Update working state must not raise
    working = resilient_service.update_working_state(
        "sess_broken", finding="Safe finding"
    )
    assert isinstance(working, WorkingMemoryState)


def test_singleton_and_factory_reset() -> None:
    """Verify get_memory_service returns singleton and reset_memory_service resets instance."""
    reset_memory_service()
    s1 = get_memory_service()
    s2 = get_memory_service()
    assert s1 is s2

    reset_memory_service()
    s3 = get_memory_service()
    assert s3 is not s1
