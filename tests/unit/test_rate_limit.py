"""Unit and integration tests for Redis token-bucket rate limiter and middleware (N6).

Verifies Redis client initialization (with fakeredis in offline mode), the token-bucket
replenishment and consumption algorithm, headers generation (X-RateLimit-*),
429 Too Many Requests responses, path exclusions, and client IP/user isolation.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.rate_limit import TokenBucketRateLimiter
from backend.app.core.redis import close_redis_client, get_redis_client
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_context import RequestContextMiddleware


def test_redis_client_offline_fakeredis():
    """Verify that get_redis_client provides an in-memory fakeredis instance in offline mode (N1)."""
    close_redis_client()
    settings = Settings(use_fakeredis=True)
    client = get_redis_client(settings=settings)
    assert client.ping() is True
    # Verify set/get operations
    client.set("test_key", "test_val")
    assert client.get("test_key") in (b"test_val", "test_val")
    close_redis_client()


def test_token_bucket_algorithm_basic_consumption_and_exhaustion():
    """Test token bucket allows requests up to capacity and rejects once exhausted."""
    close_redis_client()
    redis_client = get_redis_client()
    redis_client.flushall()

    # Create limiter: capacity=3, rate=3 tokens/60s
    limiter = TokenBucketRateLimiter(
        redis_client=redis_client,
        rate_limit_per_minute=3,
        key_prefix="test_limit",
    )

    client_id = "client_alpha"

    # 1st request -> allowed, 2 remaining
    res1 = limiter.check_rate_limit(client_id)
    assert res1.allowed is True
    assert res1.remaining == 2
    assert res1.limit == 3
    assert res1.retry_after == 0

    # 2nd request -> allowed, 1 remaining
    res2 = limiter.check_rate_limit(client_id)
    assert res2.allowed is True
    assert res2.remaining == 1

    # 3rd request -> allowed, 0 remaining
    res3 = limiter.check_rate_limit(client_id)
    assert res3.allowed is True
    assert res3.remaining == 0

    # 4th request -> exhausted, blocked with 429
    res4 = limiter.check_rate_limit(client_id)
    assert res4.allowed is False
    assert res4.remaining == 0
    assert res4.retry_after >= 1


def test_token_bucket_replenishment_over_time():
    """Test that tokens replenish gradually based on elapsed time."""
    close_redis_client()
    redis_client = get_redis_client()
    redis_client.flushall()

    # 60 tokens per minute = 1 token per second
    limiter = TokenBucketRateLimiter(
        redis_client=redis_client,
        rate_limit_per_minute=60,
        key_prefix="test_refill",
    )

    client_id = "client_beta"
    base_time = 1000.0

    # Consume all 60 tokens at base_time
    for _ in range(60):
        limiter.check_rate_limit(client_id, now=base_time)

    # 61st call at base_time is blocked
    res_blocked = limiter.check_rate_limit(client_id, now=base_time)
    assert res_blocked.allowed is False

    # Simulate 2.5 seconds later -> 2.5 tokens refilled -> 1 can be consumed
    res_refilled = limiter.check_rate_limit(client_id, now=base_time + 2.5)
    assert res_refilled.allowed is True
    assert res_refilled.remaining >= 1


def test_token_bucket_client_isolation():
    """Verify that distinct client keys do not interfere with each other's rate limits."""
    close_redis_client()
    redis_client = get_redis_client()
    redis_client.flushall()

    limiter = TokenBucketRateLimiter(
        redis_client=redis_client,
        rate_limit_per_minute=2,
        key_prefix="test_iso",
    )

    # Exhaust client A
    limiter.check_rate_limit("client_A")
    limiter.check_rate_limit("client_A")
    res_a = limiter.check_rate_limit("client_A")
    assert res_a.allowed is False

    # Client B should still have full quota
    res_b = limiter.check_rate_limit("client_B")
    assert res_b.allowed is True
    assert res_b.remaining == 1


def test_rate_limit_middleware_integration():
    """Verify ASGI RateLimitMiddleware enforces 429 status and headers on FastAPI app."""
    close_redis_client()
    redis_client = get_redis_client()
    redis_client.flushall()

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit_per_minute=3,
        redis_client=redis_client,
    )

    @app.get("/health")
    def health_endpoint():
        return {"status": "ok"}

    @app.get("/api/v1/resource")
    def resource_endpoint():
        return {"data": "valuable"}

    with TestClient(app) as client:
        # Health endpoints must be exempt from rate limiting (N4/N5)
        for _ in range(10):
            h_res = client.get("/health")
            assert h_res.status_code == 200

        # Normal resource endpoint: 3 requests allowed
        headers_client = {"X-Forwarded-For": "192.168.1.100"}
        r1 = client.get("/api/v1/resource", headers=headers_client)
        assert r1.status_code == 200
        assert r1.headers.get("X-RateLimit-Limit") == "3"
        assert r1.headers.get("X-RateLimit-Remaining") == "2"
        assert "X-RateLimit-Reset" in r1.headers

        r2 = client.get("/api/v1/resource", headers=headers_client)
        assert r2.status_code == 200
        assert r2.headers.get("X-RateLimit-Remaining") == "1"

        r3 = client.get("/api/v1/resource", headers=headers_client)
        assert r3.status_code == 200
        assert r3.headers.get("X-RateLimit-Remaining") == "0"

        # 4th request must return 429 Too Many Requests (N6)
        r4 = client.get("/api/v1/resource", headers=headers_client)
        assert r4.status_code == 429
        data4 = r4.json()
        assert "Rate limit exceeded" in data4["detail"]
        assert "Retry-After" in r4.headers
        assert int(r4.headers["Retry-After"]) >= 1
        assert r4.headers.get("X-RateLimit-Remaining") == "0"
        # X-Request-ID must be preserved on 429 error responses (N5)
        assert "X-Request-ID" in r4.headers or "x-request-id" in r4.headers

        # Another client with different IP is not affected
        headers_other = {"X-Forwarded-For": "192.168.1.200"}
        r_other = client.get("/api/v1/resource", headers=headers_other)
        assert r_other.status_code == 200
        assert r_other.headers.get("X-RateLimit-Remaining") == "2"
