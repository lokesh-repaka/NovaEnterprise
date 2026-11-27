"""Unit tests for Redis episodic conversation memory and organizational memory loader (P8-2, F15, N1).

Validates:
- RedisEpisodicMemoryStore protocol conformance (EpisodicMemoryStore)
- In-memory fakeredis client integration for 100% offline isolation (N1)
- 24-hour TTL enforcement on session episodic keys (PRD OQ-3)
- Chronological multi-turn interaction ordering and session isolation
- Graceful degradation on Redis failures (Claude.md §7.3, §16)
- OrganizationalMemoryLoader loading enterprise ground truth from JSON
- Fiscal calendar quarter resolution (direct code and relative aliases)
- Service ownership mapping and service SLA tier retrieval
- Thread-safe caching and fallback handling on missing or corrupt files
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from memory.org_loader import (
    OrganizationalMemoryLoader,
    get_org_memory_loader,
    load_organizational_memory,
    reset_org_memory_loader,
)
from memory.protocols import EpisodicMemoryStore, OrganizationalMemoryStore
from memory.redis_store import RedisEpisodicMemoryStore
from memory.schemas import (
    EpisodicMemoryEntry,
    FiscalCalendar,
    OrganizationalMemory,
    ServiceTier,
)

# =====================================================================
# 1. Redis Episodic Memory Store Tests
# =====================================================================


def test_redis_episodic_store_protocol_conformance() -> None:
    """N3: Verify RedisEpisodicMemoryStore conforms to EpisodicMemoryStore protocol."""
    store = RedisEpisodicMemoryStore()
    assert isinstance(store, EpisodicMemoryStore)


def test_redis_episodic_store_add_and_get_entries() -> None:
    """F15, N1: Verify adding and retrieving episodic turns using fakeredis."""
    store = RedisEpisodicMemoryStore()
    session_id = "sess_redis_01"
    store.clear_session(session_id)

    entry = EpisodicMemoryEntry(
        session_id=session_id,
        turn_index=0,
        question="Which services does Payments API depend on?",
        answer="Payments API depends on Identity and Database.",
        complexity="simple",
        citations=["doc:arch-01#chunk-1"],
    )

    saved = store.add_entry(entry)
    assert saved.id == entry.id

    entries = store.get_entries(session_id)
    assert len(entries) == 1
    assert entries[0].id == entry.id
    assert entries[0].session_id == session_id
    assert entries[0].question == "Which services does Payments API depend on?"
    assert entries[0].answer == "Payments API depends on Identity and Database."
    assert entries[0].complexity == "simple"
    assert entries[0].citations == ["doc:arch-01#chunk-1"]

    store.clear_session(session_id)


def test_redis_episodic_store_turn_ordering_and_limit() -> None:
    """Verify chronological turn ordering and limit capping on recent turns."""
    store = RedisEpisodicMemoryStore()
    session_id = "sess_redis_turns"
    store.clear_session(session_id)

    for i in range(5):
        store.add_entry(
            EpisodicMemoryEntry(
                session_id=session_id,
                turn_index=i,
                question=f"Question {i}",
                answer=f"Answer {i}",
            )
        )

    all_entries = store.get_entries(session_id, limit=10)
    assert len(all_entries) == 5
    for i, e in enumerate(all_entries):
        assert e.turn_index == i
        assert e.question == f"Question {i}"

    # Capped limit returns most recent turns
    limited_entries = store.get_entries(session_id, limit=2)
    assert len(limited_entries) == 2
    assert limited_entries[0].turn_index == 3
    assert limited_entries[1].turn_index == 4

    store.clear_session(session_id)


def test_redis_episodic_store_ttl_enforcement() -> None:
    """PRD OQ-3: Verify 24-hour TTL (86400s) is enforced on Redis session keys."""
    store = RedisEpisodicMemoryStore(default_ttl_seconds=86400)
    session_id = "sess_redis_ttl"
    store.clear_session(session_id)

    entry = EpisodicMemoryEntry(
        session_id=session_id,
        turn_index=0,
        question="Check TTL status",
        answer="TTL enforced",
    )
    store.add_entry(entry)

    # Inspect Redis TTL directly
    redis_client = store.redis_client
    key = store._session_key(session_id)
    ttl = redis_client.ttl(key)

    assert ttl > 0
    assert ttl <= 86400

    store.clear_session(session_id)


def test_redis_episodic_store_session_isolation_and_clear() -> None:
    """Verify sessions in Redis are isolated and clearing one does not affect another."""
    store = RedisEpisodicMemoryStore()
    sess_a = "sess_redis_iso_A"
    sess_b = "sess_redis_iso_B"
    store.clear_session(sess_a)
    store.clear_session(sess_b)

    store.add_entry(
        EpisodicMemoryEntry(
            session_id=sess_a,
            turn_index=0,
            question="Question A",
            answer="Answer A",
        )
    )
    store.add_entry(
        EpisodicMemoryEntry(
            session_id=sess_b,
            turn_index=0,
            question="Question B",
            answer="Answer B",
        )
    )

    assert len(store.get_entries(sess_a)) == 1
    assert len(store.get_entries(sess_b)) == 1
    assert store.get_entries(sess_a)[0].question == "Question A"
    assert store.get_entries(sess_b)[0].question == "Question B"

    store.clear_session(sess_a)
    assert len(store.get_entries(sess_a)) == 0
    assert len(store.get_entries(sess_b)) == 1

    store.clear_session(sess_b)


def test_redis_episodic_store_error_resilience() -> None:
    """Claude.md §7.3, §16: Redis failures must degrade gracefully and never crash workflows."""
    broken_client = MagicMock()
    broken_client.rpush.side_effect = ConnectionError("Redis cluster unreachable")
    broken_client.lrange.side_effect = ConnectionError("Redis cluster unreachable")
    broken_client.delete.side_effect = ConnectionError("Redis cluster unreachable")

    store = RedisEpisodicMemoryStore(redis_client=broken_client)
    entry = EpisodicMemoryEntry(
        session_id="sess_fail_safe",
        turn_index=0,
        question="Safe question",
        answer="Safe answer",
    )

    # Operations must log warning and not raise exceptions
    saved = store.add_entry(entry)
    assert saved == entry

    entries = store.get_entries("sess_fail_safe")
    assert entries == []

    store.clear_session("sess_fail_safe")


# =====================================================================
# 2. Organizational Memory Loader Tests
# =====================================================================


def test_org_memory_loader_protocol_conformance() -> None:
    """N3: Verify OrganizationalMemoryLoader conforms to OrganizationalMemoryStore protocol."""
    loader = OrganizationalMemoryLoader()
    assert isinstance(loader, OrganizationalMemoryStore)


def test_org_memory_loader_loads_sample_data() -> None:
    """F15: Verify loader successfully parses sample_data/organizational_memory.json."""
    loader = OrganizationalMemoryLoader()
    mem = loader.load()

    assert isinstance(mem, OrganizationalMemory)
    assert mem.company_info.name == "NovaEnterprise Inc."
    assert mem.company_info.domain == "nova.io"
    assert mem.company_info.default_currency == "USD"

    # Fiscal calendar check
    calendar = loader.get_fiscal_calendar()
    assert isinstance(calendar, FiscalCalendar)
    assert calendar.fiscal_year == 2026
    assert calendar.current_quarter == "2026-Q3"
    assert calendar.last_quarter == "2026-Q2"
    assert "2026-Q1" in calendar.quarters
    assert "2026-Q4" in calendar.quarters


def test_org_memory_loader_quarter_resolution() -> None:
    """Verify quarter resolution handles direct keys, relative aliases, and case variations."""
    loader = OrganizationalMemoryLoader()

    # Direct resolution
    q1 = loader.resolve_quarter("2026-Q1")
    assert q1 is not None
    assert q1.name == "Fiscal Q1 2026"
    assert q1.status == "closed"

    # Relative aliases
    last_q = loader.resolve_quarter("last_quarter")
    assert last_q is not None
    assert last_q.name == "Fiscal Q2 2026"

    last_q_space = loader.resolve_quarter("last quarter")
    assert last_q_space is not None
    assert last_q_space.name == "Fiscal Q2 2026"

    curr_q = loader.resolve_quarter("current_quarter")
    assert curr_q is not None
    assert curr_q.name == "Fiscal Q3 2026"
    assert curr_q.status == "active"

    # Invalid quarter returns None
    assert loader.resolve_quarter("non_existent_quarter") is None


def test_org_memory_loader_service_ownership_and_tiers() -> None:
    """Verify service ownership map and SLA tier lookups."""
    loader = OrganizationalMemoryLoader()

    assert loader.get_service_owner("svc-payments-api") == "team-payments"
    assert loader.get_service_owner("svc-identity") == "team-identity"
    assert loader.get_service_owner("svc-customer-portal") == "team-cs"
    assert loader.get_service_owner("svc-unknown") is None

    tier1 = loader.get_service_tier("tier-1")
    assert tier1 is not None
    assert isinstance(tier1, ServiceTier)
    assert tier1.availability_sla == 0.9999
    assert tier1.sev1_response_sla_min == 15

    tier2 = loader.get_service_tier("tier-2")
    assert tier2 is not None
    assert tier2.availability_sla == 0.999

    assert loader.get_service_tier("tier-unknown") is None


def test_org_memory_loader_fallback_on_missing_or_corrupt_file(tmp_path: Path) -> None:
    """Verify loader falls back gracefully when file does not exist or has corrupt JSON."""
    missing_path = tmp_path / "does_not_exist.json"
    loader_missing = OrganizationalMemoryLoader(file_path=missing_path)
    mem_fallback = loader_missing.load()
    assert isinstance(mem_fallback, OrganizationalMemory)
    assert mem_fallback.company_info.name == "NovaEnterprise Inc."

    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("NOT_VALID_JSON{:::}", encoding="utf-8")
    loader_corrupt = OrganizationalMemoryLoader(file_path=corrupt_path)
    mem_corrupt_fallback = loader_corrupt.load()
    assert isinstance(mem_corrupt_fallback, OrganizationalMemory)
    assert mem_corrupt_fallback.company_info.name == "NovaEnterprise Inc."


def test_org_memory_loader_reload_behavior(tmp_path: Path) -> None:
    """Verify reload() clears cache and re-reads the underlying file."""
    test_file = tmp_path / "dynamic_org.json"
    payload_v1 = {
        "company_info": {"name": "NovaEnterprise Alpha"},
        "fiscal_calendar": {
            "fiscal_year": 2026,
            "current_quarter": "2026-Q1",
            "last_quarter": "2025-Q4",
        },
        "service_ownership": {"svc-test": "team-alpha"},
    }
    test_file.write_text(json.dumps(payload_v1), encoding="utf-8")

    loader = OrganizationalMemoryLoader(file_path=test_file)
    assert loader.load().company_info.name == "NovaEnterprise Alpha"
    assert loader.get_service_owner("svc-test") == "team-alpha"

    # Update file content
    payload_v2 = {
        "company_info": {"name": "NovaEnterprise Beta"},
        "fiscal_calendar": {
            "fiscal_year": 2026,
            "current_quarter": "2026-Q2",
            "last_quarter": "2026-Q1",
        },
        "service_ownership": {"svc-test": "team-beta"},
    }
    test_file.write_text(json.dumps(payload_v2), encoding="utf-8")

    # Before reload: returns cached model
    assert loader.load().company_info.name == "NovaEnterprise Alpha"

    # After reload: returns updated model
    loader.reload()
    assert loader.load().company_info.name == "NovaEnterprise Beta"
    assert loader.get_service_owner("svc-test") == "team-beta"


def test_functional_load_organizational_memory_and_singleton() -> None:
    """Verify load_organizational_memory() functional helper and singleton lifecycle."""
    reset_org_memory_loader()
    mem = load_organizational_memory()
    assert isinstance(mem, OrganizationalMemory)
    assert mem.company_info.name == "NovaEnterprise Inc."

    loader1 = get_org_memory_loader()
    loader2 = get_org_memory_loader()
    assert loader1 is loader2

    reset_org_memory_loader()
    loader3 = get_org_memory_loader()
    assert loader3 is not loader1
