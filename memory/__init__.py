"""Memory subsystem for NovaEnterprise (P8-1, F15, Claude.md §7.4).

Exports:
- Four discrete memory scopes: Working, Episodic, Semantic, Organizational
- Strongly typed Pydantic models for memory items and context snapshots
- Runtime-checkable protocol specifications for memory backends
- In-memory reference stores for zero-dependency offline isolation (N1)
"""

from memory.org_loader import (
    DEFAULT_ORG_MEMORY_PATH,
    OrganizationalMemoryLoader,
    get_org_memory_loader,
    load_organizational_memory,
    reset_org_memory_loader,
)
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
from memory.redis_store import (
    DEFAULT_EPISODIC_TTL_SECONDS,
    DEFAULT_KEY_PREFIX,
    RedisEpisodicMemoryStore,
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
    "DEFAULT_EPISODIC_TTL_SECONDS",
    "DEFAULT_KEY_PREFIX",
    "DEFAULT_ORG_MEMORY_PATH",
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
    "InMemoryWorkingMemoryStore",
    "MemoryItem",
    "MemoryScope",
    "OrganizationalMemory",
    "OrganizationalMemoryLoader",
    "OrganizationalMemoryStore",
    "RedisEpisodicMemoryStore",
    "SemanticMemoryEntry",
    "SemanticMemoryStore",
    "ServiceTier",
    "UnifiedMemoryStore",
    "WorkingMemoryState",
    "WorkingMemoryStore",
    "get_org_memory_loader",
    "get_unified_memory_store",
    "load_organizational_memory",
    "reset_memory_stores",
    "reset_org_memory_loader",
]
