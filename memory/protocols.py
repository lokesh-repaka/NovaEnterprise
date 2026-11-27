"""Memory storage protocols and reference in-memory implementations (P8-1, F15, N1, N3).

Defines runtime-checkable protocols for all four memory scopes:
- WorkingMemoryStore: Transient in-node execution state
- EpisodicMemoryStore: Session multi-turn conversation history
- SemanticMemoryStore: Analyst profile and persistent learnings
- OrganizationalMemoryStore: Curated enterprise constants and fiscal calendar
- UnifiedMemoryStore: Aggregator across all four memory scopes

Provides thread-safe in-memory implementations suitable for 100% offline isolation (N1).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Protocol, runtime_checkable

from memory.schemas import (
    EpisodicMemoryEntry,
    FiscalCalendar,
    FourScopeMemoryContext,
    OrganizationalMemory,
    SemanticMemoryEntry,
    ServiceTier,
    WorkingMemoryState,
)

# =====================================================================
# 1. Scope Protocol Definitions
# =====================================================================


@runtime_checkable
class WorkingMemoryStore(Protocol):
    """Storage protocol for transient in-node working memory."""

    def get_state(self, session_id: str) -> WorkingMemoryState | None:
        """Retrieve current working state for session."""
        ...

    def save_state(self, session_id: str, state: WorkingMemoryState) -> None:
        """Save or update working state for session."""
        ...

    def clear_state(self, session_id: str) -> None:
        """Clear active working state for session."""
        ...


@runtime_checkable
class EpisodicMemoryStore(Protocol):
    """Storage protocol for session-level conversation turns and research history."""

    def add_entry(self, entry: EpisodicMemoryEntry) -> EpisodicMemoryEntry:
        """Record an interaction turn in episodic memory."""
        ...

    def get_entries(
        self, session_id: str, limit: int = 10
    ) -> list[EpisodicMemoryEntry]:
        """Retrieve chronological interaction turns for a session."""
        ...

    def clear_session(self, session_id: str) -> None:
        """Remove all episodic memory entries for a session."""
        ...


@runtime_checkable
class SemanticMemoryStore(Protocol):
    """Storage protocol for persistent analyst-level knowledge and preferences."""

    def add_entry(self, entry: SemanticMemoryEntry) -> SemanticMemoryEntry:
        """Save or update an analyst semantic memory entry."""
        ...

    def get_entries(
        self, user_id: str, category: str | None = None
    ) -> list[SemanticMemoryEntry]:
        """Retrieve all semantic entries for a user, optionally filtered by category."""
        ...

    def get_entry_by_key(self, user_id: str, key: str) -> SemanticMemoryEntry | None:
        """Retrieve a specific semantic entry by key for a user."""
        ...

    def delete_entry(self, user_id: str, entry_id: str) -> bool:
        """Delete a specific semantic entry by ID."""
        ...

    def clear_user_memory(self, user_id: str) -> None:
        """Remove all semantic memory entries for a user."""
        ...


@runtime_checkable
class OrganizationalMemoryStore(Protocol):
    """Storage protocol for company-wide constants and fiscal calendar."""

    def load(self) -> OrganizationalMemory:
        """Retrieve full organizational memory model."""
        ...

    def get_fiscal_calendar(self) -> FiscalCalendar:
        """Retrieve corporate fiscal calendar."""
        ...

    def get_service_owner(self, service_id: str) -> str | None:
        """Retrieve team ID owning a specific service."""
        ...

    def get_service_tier(self, tier_id: str) -> ServiceTier | None:
        """Retrieve SLA specifications for a service tier."""
        ...


@runtime_checkable
class UnifiedMemoryStore(Protocol):
    """Unified coordinator protocol orchestrating all 4 memory scopes."""

    working: WorkingMemoryStore
    episodic: EpisodicMemoryStore
    semantic: SemanticMemoryStore
    organizational: OrganizationalMemoryStore

    def assemble_context(
        self, session_id: str, user_id: str | None = None
    ) -> FourScopeMemoryContext:
        """Assemble a FourScopeMemoryContext snapshot across all four tiers."""
        ...


# =====================================================================
# 2. In-Memory Store Implementations (Offline Isolation N1)
# =====================================================================


class InMemoryWorkingMemoryStore:
    """Thread-safe in-memory store for working memory."""

    def __init__(self) -> None:
        self._states: dict[str, WorkingMemoryState] = {}
        self._lock = threading.Lock()

    def get_state(self, session_id: str) -> WorkingMemoryState | None:
        """Retrieve working state for session."""
        with self._lock:
            state = self._states.get(session_id)
            return state.model_copy(deep=True) if state else None

    def save_state(self, session_id: str, state: WorkingMemoryState) -> None:
        """Save or update working state for session."""
        with self._lock:
            self._states[session_id] = state.model_copy(deep=True)

    def clear_state(self, session_id: str) -> None:
        """Clear active working state for session."""
        with self._lock:
            self._states.pop(session_id, None)


class InMemoryEpisodicMemoryStore:
    """Thread-safe in-memory store for episodic conversation memory."""

    def __init__(self) -> None:
        self._entries: dict[str, list[EpisodicMemoryEntry]] = {}
        self._lock = threading.Lock()

    def add_entry(self, entry: EpisodicMemoryEntry) -> EpisodicMemoryEntry:
        """Record an interaction turn."""
        with self._lock:
            if entry.session_id not in self._entries:
                self._entries[entry.session_id] = []
            self._entries[entry.session_id].append(entry.model_copy(deep=True))
            # Sort chronologically by turn_index
            self._entries[entry.session_id].sort(key=lambda e: e.turn_index)
            return entry

    def get_entries(
        self, session_id: str, limit: int = 10
    ) -> list[EpisodicMemoryEntry]:
        """Retrieve turns for a session in chronological order up to limit."""
        with self._lock:
            session_entries = self._entries.get(session_id, [])
            return [e.model_copy(deep=True) for e in session_entries[-limit:]]

    def clear_session(self, session_id: str) -> None:
        """Remove all episodic memory entries for a session."""
        with self._lock:
            self._entries.pop(session_id, None)


class InMemorySemanticMemoryStore:
    """Thread-safe in-memory store for analyst semantic memory."""

    def __init__(self) -> None:
        # user_id -> dict of entry_id -> entry
        self._user_entries: dict[str, dict[str, SemanticMemoryEntry]] = {}
        self._lock = threading.Lock()

    def add_entry(self, entry: SemanticMemoryEntry) -> SemanticMemoryEntry:
        """Save or update an analyst semantic memory entry."""
        with self._lock:
            if entry.user_id not in self._user_entries:
                self._user_entries[entry.user_id] = {}
            # Check for existing key to overwrite if present
            for existing_id, existing in list(
                self._user_entries[entry.user_id].items()
            ):
                if existing.key == entry.key:
                    self._user_entries[entry.user_id].pop(existing_id, None)
                    break
            self._user_entries[entry.user_id][entry.id] = entry.model_copy(deep=True)
            return entry

    def get_entries(
        self, user_id: str, category: str | None = None
    ) -> list[SemanticMemoryEntry]:
        """Retrieve all semantic entries for a user, optionally filtered by category."""
        with self._lock:
            user_dict = self._user_entries.get(user_id, {})
            entries = list(user_dict.values())
            if category:
                entries = [e for e in entries if e.category.lower() == category.lower()]
            return [e.model_copy(deep=True) for e in entries]

    def get_entry_by_key(self, user_id: str, key: str) -> SemanticMemoryEntry | None:
        """Retrieve a specific semantic entry by key for a user."""
        with self._lock:
            user_dict = self._user_entries.get(user_id, {})
            for entry in user_dict.values():
                if entry.key == key:
                    return entry.model_copy(deep=True)
            return None

    def delete_entry(self, user_id: str, entry_id: str) -> bool:
        """Delete a specific semantic entry by ID."""
        with self._lock:
            user_dict = self._user_entries.get(user_id, {})
            if entry_id in user_dict:
                user_dict.pop(entry_id)
                return True
            return False

    def clear_user_memory(self, user_id: str) -> None:
        """Remove all semantic memory entries for a user."""
        with self._lock:
            self._user_entries.pop(user_id, None)


class InMemoryOrganizationalMemoryStore:
    """Thread-safe in-memory store for enterprise constants and fiscal calendar."""

    def __init__(
        self,
        memory: OrganizationalMemory | None = None,
        source_path: Path | str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        if memory is not None:
            self._memory = memory
        elif source_path is not None and Path(source_path).exists():
            self._memory = OrganizationalMemory.from_file(source_path)
        else:
            default_sample = Path("sample_data/organizational_memory.json")
            if default_sample.exists():
                self._memory = OrganizationalMemory.from_file(default_sample)
            else:
                self._memory = OrganizationalMemory()

    def load(self) -> OrganizationalMemory:
        """Retrieve full organizational memory model."""
        with self._lock:
            return self._memory.model_copy(deep=True)

    def get_fiscal_calendar(self) -> FiscalCalendar:
        """Retrieve corporate fiscal calendar."""
        with self._lock:
            return self._memory.fiscal_calendar.model_copy(deep=True)

    def get_service_owner(self, service_id: str) -> str | None:
        """Retrieve team ID owning a specific service."""
        with self._lock:
            return self._memory.get_service_owner(service_id)

    def get_service_tier(self, tier_id: str) -> ServiceTier | None:
        """Retrieve SLA specifications for a service tier."""
        with self._lock:
            tier = self._memory.get_service_tier(tier_id)
            return tier.model_copy(deep=True) if tier else None


class InMemoryUnifiedMemoryStore:
    """Thread-safe coordinator coordinating across all four in-memory stores."""

    def __init__(
        self,
        working: WorkingMemoryStore | None = None,
        episodic: EpisodicMemoryStore | None = None,
        semantic: SemanticMemoryStore | None = None,
        organizational: OrganizationalMemoryStore | None = None,
    ) -> None:
        self.working: WorkingMemoryStore = (
            working if working is not None else InMemoryWorkingMemoryStore()
        )
        self.episodic: EpisodicMemoryStore = (
            episodic if episodic is not None else InMemoryEpisodicMemoryStore()
        )
        self.semantic: SemanticMemoryStore = (
            semantic if semantic is not None else InMemorySemanticMemoryStore()
        )
        self.organizational: OrganizationalMemoryStore = (
            organizational
            if organizational is not None
            else InMemoryOrganizationalMemoryStore()
        )

    def assemble_context(
        self, session_id: str, user_id: str | None = None
    ) -> FourScopeMemoryContext:
        """Assemble a FourScopeMemoryContext snapshot across all four memory scopes."""
        working_state = self.working.get_state(session_id) or WorkingMemoryState(
            session_id=session_id
        )
        episodic_entries = self.episodic.get_entries(session_id=session_id)
        semantic_entries = self.semantic.get_entries(user_id=user_id) if user_id else []
        org_memory = self.organizational.load()

        return FourScopeMemoryContext(
            session_id=session_id,
            user_id=user_id,
            working=working_state,
            episodic=episodic_entries,
            semantic=semantic_entries,
            organizational=org_memory,
        )


# =====================================================================
# 3. Global Singletons & Factory Functions
# =====================================================================

_unified_store_instance: InMemoryUnifiedMemoryStore | None = None
_store_lock = threading.Lock()


def get_unified_memory_store() -> InMemoryUnifiedMemoryStore:
    """Retrieve application-wide unified memory store singleton."""
    global _unified_store_instance
    if _unified_store_instance is None:
        with _store_lock:
            if _unified_store_instance is None:
                _unified_store_instance = InMemoryUnifiedMemoryStore()
    return _unified_store_instance


def reset_memory_stores() -> None:
    """Reset application-wide memory store instances (for test isolation)."""
    global _unified_store_instance
    with _store_lock:
        _unified_store_instance = None
