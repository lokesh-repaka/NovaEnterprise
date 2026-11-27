"""Memory subsystem for NovaEnterprise (P8-1, F15, Claude.md §7.4).

Exports:
- Four discrete memory scopes: Working, Episodic, Semantic, Organizational
- Strongly typed Pydantic models for memory items and context snapshots
- Runtime-checkable protocol specifications for memory backends
- In-memory reference stores for zero-dependency offline isolation (N1)
"""

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
    get_unified_memory_store,
    reset_memory_stores,
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

__all__ = [
    "CompanyInfo",
    "EpisodicMemoryEntry",
    "EpisodicMemoryStore",
    "FiscalCalendar",
    "FiscalQuarter",
    "FourScopeMemoryContext",
    "InMemoryEpisodicMemoryStore",
    "InMemoryOrganizationalMemoryStore",
    "InMemorySemanticMemoryStore",
    "InMemoryUnifiedMemoryStore",
    # In-Memory Store Implementations
    "InMemoryWorkingMemoryStore",
    "MemoryItem",
    # Scopes & Items
    "MemoryScope",
    "OrganizationalMemory",
    "OrganizationalMemoryStore",
    "SemanticMemoryEntry",
    "SemanticMemoryStore",
    "ServiceTier",
    "UnifiedMemoryStore",
    # Scope Models
    "WorkingMemoryState",
    # Protocols
    "WorkingMemoryStore",
    # Singletons
    "get_unified_memory_store",
    "reset_memory_stores",
]
