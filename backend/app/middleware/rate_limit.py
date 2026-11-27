"""Token-bucket rate limiting ASGI middleware (N6).

Intercepts incoming requests, applies Redis-backed token bucket rate limits
per client IP or authenticated user, appends standard X-RateLimit-* headers,
and returns 429 Too Many Requests when limits are exhausted.
"""

import hashlib
import uuid
from collections.abc import Set as AbstractSet

import redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.app.core.config import get_settings
from backend.app.core.rate_limit import TokenBucketRateLimiter
from backend.app.middleware.request_context import REQUEST_ID_HEADER

DEFAULT_EXEMPT_PATHS: set[str] = {
    "/health",
    "/health/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware applying token-bucket rate limits per client."""

    def __init__(
        self,
        app: ASGIApp,
        rate_limit_per_minute: int | None = None,
        redis_client: redis.Redis | None = None,
        exempt_paths: AbstractSet[str] | None = None,
    ) -> None:
        super().__init__(app)
        settings = get_settings()
        limit = (
            rate_limit_per_minute
            if rate_limit_per_minute is not None
            else settings.rate_limit_per_minute
        )
        self.limiter = TokenBucketRateLimiter(
            redis_client=redis_client,
            rate_limit_per_minute=limit,
        )
        self.exempt_paths = (
            set(exempt_paths) if exempt_paths is not None else DEFAULT_EXEMPT_PATHS
        )

    def _extract_client_key(self, request: Request) -> str:
        """Resolve a rate limit bucket key from Authorization or client IP."""
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
                return f"token:{token_hash}"

        # Fallback to forwarded IP or direct socket host
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded and forwarded.strip():
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        return f"ip:{client_ip}"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check client token bucket quota before delegating to downstream handlers."""
        # Check path exemption (e.g. /health, /docs)
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_key = self._extract_client_key(request)
        result = self.limiter.check_rate_limit(client_key)

        # Rate limit exceeded -> return 429 Too Many Requests (N6)
        if not result.allowed:
            # Preserve or generate request ID for tracing (N5)
            request_id = getattr(request.state, "request_id", None)
            if not request_id:
                request_id = request.headers.get("x-request-id") or request.headers.get(
                    REQUEST_ID_HEADER
                )
            if not request_id or not str(request_id).strip():
                request_id = str(uuid.uuid4())

            headers = {
                "Retry-After": str(result.retry_after),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset),
                REQUEST_ID_HEADER: str(request_id),
            }

            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many requests. Rate limit exceeded. Retry after {result.retry_after} seconds."
                },
                headers=headers,
            )

        # Proceed with downstream execution
        response = await call_next(request)

        # Append standard rate limit tracking headers to response
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset)

        return response
