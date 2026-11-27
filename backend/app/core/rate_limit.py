"""Token bucket rate limiter backed by Redis (N6).

Enforces configurable request limits (RATE_LIMIT_PER_MINUTE, default 120)
using an atomic token-bucket replenishment and consumption model.
"""

import math
import time
from dataclasses import dataclass

import redis

from backend.app.core.config import get_settings
from backend.app.core.redis import get_redis_client


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate limit consumption check."""

    allowed: bool
    limit: int
    remaining: int
    reset: int
    retry_after: int


class TokenBucketRateLimiter:
    """Thread-safe token-bucket rate limiter utilizing Redis hashes."""

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        rate_limit_per_minute: int | None = None,
        key_prefix: str = "rate_limit",
    ) -> None:
        settings = get_settings()
        self.redis = (
            redis_client if redis_client is not None else get_redis_client(settings)
        )
        self.capacity = float(
            rate_limit_per_minute
            if rate_limit_per_minute is not None
            else settings.rate_limit_per_minute
        )
        self.refill_rate = self.capacity / 60.0  # Tokens refilled per second
        self.key_prefix = key_prefix
        # TTL for key expiration to prevent stale keys in Redis
        self.ttl = max(120, int(self.capacity / max(self.refill_rate, 0.01)) * 2)

    def check_rate_limit(
        self,
        client_key: str,
        cost: float = 1.0,
        now: float | None = None,
    ) -> RateLimitResult:
        """Evaluate if an action is permissible under the token bucket limits.

        Replenishes tokens proportional to elapsed time since last request,
        decrements by cost if sufficient tokens exist, and updates Redis atomically.
        """
        current_time = time.time() if now is None else now
        redis_key = f"{self.key_prefix}:{client_key}"

        # Fetch current bucket state from Redis
        raw = self.redis.hmget(redis_key, ["tokens", "last_refreshed"])  # type: ignore[arg-type]
        tokens_raw, last_refreshed_raw = raw[0], raw[1]

        if tokens_raw is None or last_refreshed_raw is None:
            # First request: start with full capacity
            tokens = self.capacity
            last_refreshed = current_time
        else:
            try:
                tokens = float(tokens_raw)
                last_refreshed = float(last_refreshed_raw)
            except (ValueError, TypeError):
                tokens = self.capacity
                last_refreshed = current_time

            # Replenish tokens based on elapsed duration
            delta = max(0.0, current_time - last_refreshed)
            tokens = min(self.capacity, tokens + (delta * self.refill_rate))
            last_refreshed = current_time

        # Check allowance
        if tokens >= cost:
            allowed = True
            tokens -= cost
            retry_after = 0
        else:
            allowed = False
            deficit = cost - tokens
            retry_after = max(1, math.ceil(deficit / self.refill_rate))

        # Persist updated bucket state back to Redis
        pipe = self.redis.pipeline()
        pipe.hset(
            redis_key,
            mapping={
                "tokens": str(tokens),
                "last_refreshed": str(last_refreshed),
            },
        )
        pipe.expire(redis_key, self.ttl)
        pipe.execute()

        remaining = max(0, int(tokens))
        reset = max(1, math.ceil((self.capacity - tokens) / self.refill_rate))

        return RateLimitResult(
            allowed=allowed,
            limit=int(self.capacity),
            remaining=remaining,
            reset=reset,
            retry_after=retry_after,
        )
