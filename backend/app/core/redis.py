"""Redis connection manager and client lifecycle (N1, N6).

Provides thread-safe Redis client access, supporting in-memory fakeredis
for offline environments (N1) and external Redis clusters in production.
"""

import contextlib
from typing import Any

import fakeredis
import redis

from backend.app.core.config import Settings, get_settings

_redis_client: redis.Redis | None = None
_fake_server: fakeredis.FakeServer | None = None


def get_redis_client(settings: Settings | None = None) -> redis.Redis:
    """Retrieve or initialize the active Redis client.

    If settings.use_fakeredis is True, uses an in-memory FakeServer so all
    application threads and middleware share state without external dependencies.
    """
    global _redis_client, _fake_server

    if _redis_client is not None:
        return _redis_client

    if settings is None:
        settings = get_settings()

    if settings.use_fakeredis:
        if _fake_server is None:
            _fake_server = fakeredis.FakeServer()
        _redis_client = fakeredis.FakeRedis(
            server=_fake_server,
            decode_responses=True,
        )
    else:
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    return _redis_client


def close_redis_client() -> None:
    """Close active client connection and reset global state (for test cleanup)."""
    global _redis_client, _fake_server
    if _redis_client is not None:
        with contextlib.suppress(Exception):
            _redis_client.close()
        _redis_client = None
    _fake_server = None


def check_redis_connection(settings: Settings | None = None) -> dict[str, Any]:
    """Test connectivity to Redis and return diagnostic status dictionary."""
    if settings is None:
        settings = get_settings()

    try:
        client = get_redis_client(settings)
        is_alive = bool(client.ping())
        if is_alive:
            detail = (
                "fakeredis (in-memory)"
                if settings.use_fakeredis
                else f"redis: {settings.redis_url}"
            )
            return {"status": "ok", "detail": detail}
        return {"status": "degraded", "detail": "Redis ping returned False"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "detail": f"Redis connection error: {e!s}"}
