"""Redis episodic conversation memory store for NovaEnterprise (P8-2, F15, N1, Claude.md §7.4).

Provides RedisEpisodicMemoryStore conforming to EpisodicMemoryStore protocol:
- Backed by Redis (or in-memory fakeredis for 100% offline isolation N1)
- Key naming scheme: nova:memory:session:{session_id}:turns
- Automatic 24-hour TTL expiration per session (PRD OQ-3)
- Chronological ordering of multi-turn conversation history
- Fail-safe execution: Redis outages degrade gracefully and never crash workflows
"""

from __future__ import annotations

import json
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.core.redis import get_redis_client
from memory.schemas import EpisodicMemoryEntry

logger = get_logger("memory.redis_store")

DEFAULT_EPISODIC_TTL_SECONDS: int = 86400  # 24 hours per PRD OQ-3
DEFAULT_KEY_PREFIX: str = "nova:memory:session"


class RedisEpisodicMemoryStore:
    """Redis-backed store for multi-turn episodic conversation memory (F15).

    Conforms to the EpisodicMemoryStore protocol.
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        default_ttl_seconds: int = DEFAULT_EPISODIC_TTL_SECONDS,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> None:
        self._client = redis_client
        self.default_ttl_seconds = default_ttl_seconds
        self.key_prefix = key_prefix

    @property
    def redis_client(self) -> Any:
        """Lazily retrieve active Redis client (real Redis or fakeredis)."""
        if self._client is None:
            self._client = get_redis_client()
        return self._client

    def _session_key(self, session_id: str) -> str:
        """Format Redis key for session episodic turns."""
        return f"{self.key_prefix}:{session_id}:turns"

    def add_entry(self, entry: EpisodicMemoryEntry) -> EpisodicMemoryEntry:
        """Record an interaction turn in Redis and refresh session TTL.

        Guarantees:
        - Serializes entry to JSON string.
        - Pushes to Redis list tail.
        - Sets TTL expiration on the session key.
        - Swallows errors gracefully if Redis is temporarily degraded.
        """
        key = self._session_key(entry.session_id)
        ttl = entry.ttl_seconds or self.default_ttl_seconds

        try:
            payload_str = entry.model_dump_json()
            client = self.redis_client
            client.rpush(key, payload_str)
            if ttl > 0:
                client.expire(key, ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to record episodic memory in Redis for session '%s': %s",
                entry.session_id,
                exc,
            )

        return entry

    def get_entries(
        self, session_id: str, limit: int = 10
    ) -> list[EpisodicMemoryEntry]:
        """Retrieve interaction turns for a session in chronological order up to limit."""
        key = self._session_key(session_id)
        try:
            client = self.redis_client
            # Fetch items from Redis list
            raw_items = client.lrange(key, 0, -1)
            if not raw_items:
                return []

            entries: list[EpisodicMemoryEntry] = []
            for item in raw_items:
                try:
                    if isinstance(item, bytes):
                        item_str = item.decode("utf-8")
                    else:
                        item_str = str(item)
                    entry_dict = json.loads(item_str)
                    entries.append(EpisodicMemoryEntry.model_validate(entry_dict))
                except Exception as parse_err:  # noqa: BLE001
                    logger.debug("Skipping unparseable episodic item: %s", parse_err)

            # Chronologically sort by turn_index
            entries.sort(key=lambda e: e.turn_index)

            # Return most recent up to limit
            return entries[-limit:]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to retrieve episodic memory from Redis for session '%s': %s",
                session_id,
                exc,
            )
            return []

    def clear_session(self, session_id: str) -> None:
        """Remove all episodic memory entries for a session."""
        key = self._session_key(session_id)
        try:
            client = self.redis_client
            client.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to clear episodic memory in Redis for session '%s': %s",
                session_id,
                exc,
            )
