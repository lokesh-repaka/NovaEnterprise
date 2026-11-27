"""Unified memory recall and update service for NovaEnterprise (P8-3, F15, N1, N3, Claude.md §7.4).

Provides MemoryService (MemoryFacade) orchestrating the four memory scopes:
1. Working Memory (in-node / StateGraph execution run transient state)
2. Episodic Memory (Redis-backed session multi-turn conversation history)
3. Semantic Memory (Analyst profile, preferences, and domain insights)
4. Organizational Memory (Curated enterprise ground truth and fiscal calendar)

Guarantees:
- Strict scope separation: memory is never intermingled with retrieval indices.
- Fail-safe resilience: memory failures degrade gracefully and never break workflow runs.
- Analyst boundary isolation: analysts manage only their own semantic memory.
- Conforms to UnifiedMemoryStore protocol.
"""

from __future__ import annotations

import threading
from typing import Any

from backend.app.core.logging import get_logger
from memory.org_loader import get_org_memory_loader
from memory.protocols import (
    EpisodicMemoryStore,
    InMemorySemanticMemoryStore,
    InMemoryWorkingMemoryStore,
    OrganizationalMemoryStore,
    SemanticMemoryStore,
    WorkingMemoryStore,
)
from memory.redis_store import RedisEpisodicMemoryStore
from memory.schemas import (
    EpisodicMemoryEntry,
    FiscalQuarter,
    FourScopeMemoryContext,
    OrganizationalMemory,
    SemanticMemoryEntry,
    ServiceTier,
    WorkingMemoryState,
)

logger = get_logger("memory.service")


class MemoryService:
    """Unified coordinator service for recall and updates across all four memory scopes (F15).

    Conforms to the UnifiedMemoryStore protocol.
    """

    def __init__(
        self,
        working_store: WorkingMemoryStore | None = None,
        episodic_store: EpisodicMemoryStore | None = None,
        semantic_store: SemanticMemoryStore | None = None,
        org_store: OrganizationalMemoryStore | None = None,
    ) -> None:
        self.working: WorkingMemoryStore = (
            working_store if working_store is not None else InMemoryWorkingMemoryStore()
        )
        self.episodic: EpisodicMemoryStore = (
            episodic_store if episodic_store is not None else RedisEpisodicMemoryStore()
        )
        self.semantic: SemanticMemoryStore = (
            semantic_store
            if semantic_store is not None
            else InMemorySemanticMemoryStore()
        )
        self.organizational: OrganizationalMemoryStore = (
            org_store if org_store is not None else get_org_memory_loader()
        )

    # =====================================================================
    # Unified Snapshot Recall
    # =====================================================================

    def assemble_context(
        self, session_id: str, user_id: str | None = None
    ) -> FourScopeMemoryContext:
        """Protocol method alias for recall()."""
        return self.recall(session_id=session_id, user_id=user_id)

    def recall(
        self, session_id: str, user_id: str | None = None
    ) -> FourScopeMemoryContext:
        """Recall a unified FourScopeMemoryContext snapshot across all four memory scopes."""
        try:
            working_state = self.get_working_state(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to recall working memory for '%s': %s", session_id, exc
            )
            working_state = WorkingMemoryState(session_id=session_id)

        try:
            episodic_entries = self.get_episodic_history(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to recall episodic memory for '%s': %s", session_id, exc
            )
            episodic_entries = []

        try:
            semantic_entries = self.get_semantic_knowledge(user_id) if user_id else []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to recall semantic memory for user '%s': %s", user_id, exc
            )
            semantic_entries = []

        try:
            org_memory = self.get_organizational_memory()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to recall organizational memory: %s", exc)
            org_memory = OrganizationalMemory()

        return FourScopeMemoryContext(
            session_id=session_id,
            user_id=user_id,
            working=working_state,
            episodic=episodic_entries,
            semantic=semantic_entries,
            organizational=org_memory,
        )

    def recall_prompt_context(self, session_id: str, user_id: str | None = None) -> str:
        """Retrieve memory context formatted as safe Markdown for LLM prompt context injection."""
        context = self.recall(session_id=session_id, user_id=user_id)
        return context.to_prompt_context()

    # =====================================================================
    # Scope 1: Working Memory Operations
    # =====================================================================

    def get_working_state(self, session_id: str) -> WorkingMemoryState:
        """Retrieve active working state for a session, returning fresh state if absent."""
        try:
            state = self.working.get_state(session_id)
            if state is not None:
                return state
        except Exception as exc:  # noqa: BLE001
            logger.warning("Working store lookup failed for '%s': %s", session_id, exc)
        return WorkingMemoryState(session_id=session_id)

    def update_working_state(
        self,
        session_id: str,
        active_sub_question: str | None = None,
        sub_question_index: int | None = None,
        finding: str | None = None,
        scratchpad_update: dict[str, Any] | None = None,
        last_node: str | None = None,
    ) -> WorkingMemoryState:
        """Incrementally mutate the in-run working memory state."""
        state = self.get_working_state(session_id)

        if active_sub_question is not None:
            state.set_active_sub_question(active_sub_question, index=sub_question_index)
        elif sub_question_index is not None:
            state.current_sub_question_index = sub_question_index

        if finding:
            state.add_finding(finding)

        if scratchpad_update:
            for k, v in scratchpad_update.items():
                state.update_scratchpad(k, v)

        if last_node:
            state.last_node = last_node

        try:
            self.working.save_state(session_id, state)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save working state for '%s': %s", session_id, exc)

        return state

    # =====================================================================
    # Scope 2: Episodic Memory Operations
    # =====================================================================

    def get_episodic_history(
        self, session_id: str, limit: int = 10
    ) -> list[EpisodicMemoryEntry]:
        """Retrieve recent interaction turns for a session in chronological order."""
        try:
            return self.episodic.get_entries(session_id=session_id, limit=limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to retrieve episodic history for '%s': %s", session_id, exc
            )
            return []

    def update_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        citations: list[str] | None = None,
        complexity: str | None = None,
        user_id: str | None = None,
        feedback: str | None = None,
    ) -> EpisodicMemoryEntry:
        """Record a completed interaction turn into episodic memory with auto-incremented index."""
        try:
            existing = self.episodic.get_entries(session_id=session_id, limit=100)
            next_turn_index = max(e.turn_index for e in existing) + 1 if existing else 0
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to check existing turn indices for '%s': %s", session_id, exc
            )
            next_turn_index = 0

        entry = EpisodicMemoryEntry(
            session_id=session_id,
            turn_index=next_turn_index,
            user_id=user_id,
            question=question,
            answer=answer,
            citations=citations or [],
            complexity=complexity,
            feedback=feedback,
        )

        try:
            return self.episodic.add_entry(entry)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to append episodic entry for '%s': %s", session_id, exc
            )
            return entry

    # =====================================================================
    # Scope 3: Semantic Memory Operations
    # =====================================================================

    def get_semantic_knowledge(
        self, user_id: str, category: str | None = None
    ) -> list[SemanticMemoryEntry]:
        """Retrieve semantic knowledge entries for a specific analyst user."""
        try:
            return self.semantic.get_entries(user_id=user_id, category=category)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to retrieve semantic knowledge for user '%s': %s", user_id, exc
            )
            return []

    def save_semantic_insight(
        self,
        user_id: str,
        key: str,
        content: str,
        category: str = "preference",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> SemanticMemoryEntry:
        """Record or update an analyst preference or domain insight."""
        entry = SemanticMemoryEntry(
            user_id=user_id,
            key=key,
            content=content,
            category=category,
            confidence=confidence,
            metadata=metadata or {},
        )
        try:
            return self.semantic.add_entry(entry)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to save semantic insight for user '%s': %s", user_id, exc
            )
            return entry

    def delete_semantic_insight(self, user_id: str, entry_id: str) -> bool:
        """Delete an analyst semantic memory entry."""
        try:
            return self.semantic.delete_entry(user_id=user_id, entry_id=entry_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to delete semantic insight '%s' for user '%s': %s",
                entry_id,
                user_id,
                exc,
            )
            return False

    def clear_user_semantic_memory(self, user_id: str) -> None:
        """Purge all semantic memory entries for a specific analyst user."""
        try:
            self.semantic.clear_user_memory(user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to clear semantic memory for user '%s': %s", user_id, exc
            )

    # =====================================================================
    # Scope 4: Organizational Memory Operations
    # =====================================================================

    def get_organizational_memory(self) -> OrganizationalMemory:
        """Retrieve full corporate organizational memory model."""
        try:
            return self.organizational.load()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load organizational memory: %s", exc)
            return OrganizationalMemory()

    def resolve_quarter(self, identifier: str) -> FiscalQuarter | None:
        """Resolve a quarter by code or relative alias (e.g. 'last_quarter')."""
        try:
            return self.get_organizational_memory().fiscal_calendar.resolve_quarter(
                identifier
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to resolve quarter '%s': %s", identifier, exc)
            return None

    def get_service_owner(self, service_id: str) -> str | None:
        """Retrieve team owning a specific service."""
        try:
            return self.organizational.get_service_owner(service_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to get service owner for '%s': %s", service_id, exc)
            return None

    def get_service_tier(self, tier_id: str) -> ServiceTier | None:
        """Retrieve SLA specifications for a service tier."""
        try:
            return self.organizational.get_service_tier(tier_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to get service tier for '%s': %s", tier_id, exc)
            return None

    # =====================================================================
    # Lifecycle & Cleanup Operations
    # =====================================================================

    def clear_session_memory(self, session_id: str) -> None:
        """Purge both working state and episodic conversation history for a session."""
        try:
            self.working.clear_state(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to clear working state for '%s': %s", session_id, exc
            )

        try:
            self.episodic.clear_session(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to clear episodic history for '%s': %s", session_id, exc
            )


# =====================================================================
# Global Singleton & Lifecycle Functions
# =====================================================================

_memory_service_instance: MemoryService | None = None
_service_lock = threading.Lock()


def get_memory_service(
    working_store: WorkingMemoryStore | None = None,
    episodic_store: EpisodicMemoryStore | None = None,
    semantic_store: SemanticMemoryStore | None = None,
    org_store: OrganizationalMemoryStore | None = None,
) -> MemoryService:
    """Retrieve application-wide MemoryService singleton."""
    global _memory_service_instance
    if _memory_service_instance is None:
        with _service_lock:
            if _memory_service_instance is None:
                _memory_service_instance = MemoryService(
                    working_store=working_store,
                    episodic_store=episodic_store,
                    semantic_store=semantic_store,
                    org_store=org_store,
                )
    return _memory_service_instance


def reset_memory_service() -> None:
    """Reset application-wide MemoryService instance (for test isolation)."""
    global _memory_service_instance
    with _service_lock:
        _memory_service_instance = None
