"""State-changing request audit trail middleware (N5, P3-4).

Intercepts state-mutating HTTP operations (POST, PUT, PATCH, DELETE) and records
immutable audit log entries to PostgreSQL/SQLite via AuditLogRepository.
"""

import contextlib
from collections.abc import Set as AbstractSet

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.app.core.db import get_session_factory
from backend.app.core.logging import get_logger
from backend.app.core.security import decode_access_token
from backend.app.middleware.request_context import REQUEST_ID_HEADER
from backend.app.repositories.security import AuditLogRepository

logger = get_logger("app.middleware.audit")

STATE_CHANGING_METHODS: set[str] = {"POST", "PUT", "PATCH", "DELETE"}

DEFAULT_EXEMPT_AUDIT_PATHS: set[str] = {
    "/health",
    "/health/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}


class AuditMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for strictly append-only audit logging of state-changing requests."""

    def __init__(
        self,
        app: ASGIApp,
        exempt_paths: AbstractSet[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.exempt_paths = (
            set(exempt_paths)
            if exempt_paths is not None
            else DEFAULT_EXEMPT_AUDIT_PATHS
        )

    def _extract_user_id(self, request: Request) -> str | None:
        """Extract authenticated user identity from request state or Authorization header."""
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return str(user.id)

        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                with contextlib.suppress(Exception):
                    payload = decode_access_token(token)
                    sub = payload.get("sub")
                    if sub:
                        return str(sub)
        return None

    def _extract_resource_details(self, path: str) -> tuple[str, str | None]:
        """Parse resource type and identifier from URL path."""
        segments = [
            seg
            for seg in path.strip("/").split("/")
            if seg and seg not in ("api", "v1")
        ]
        if not segments:
            return "root", None

        resource_type = segments[0]
        resource_id = segments[1] if len(segments) > 1 else None
        return resource_type, resource_id

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and asynchronously persist audit log for state modifications."""
        # Execute downstream request pipeline first
        response = await call_next(request)

        # Check if method is state-changing (POST, PUT, PATCH, DELETE)
        method = request.method.upper()
        if method not in STATE_CHANGING_METHODS:
            return response

        # Check path exemption
        path = request.url.path
        if path in self.exempt_paths:
            return response

        # Extract audit details
        resource_type, resource_id = self._extract_resource_details(path)
        action = f"{method} {path}"

        # Request ID correlation (N5)
        request_id = getattr(request.state, "request_id", None)
        if not request_id:
            request_id = request.headers.get("x-request-id") or request.headers.get(
                REQUEST_ID_HEADER
            )

        # Client IP resolution
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded and forwarded.strip():
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = None

        user_id = self._extract_user_id(request)

        # Persist append-only audit record (fail-open so transient DB failures do not break client response)
        try:
            session_factory = get_session_factory()
            with session_factory() as db:
                repo = AuditLogRepository(db)
                repo.record_log(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    request_id=str(request_id) if request_id else None,
                    ip_address=client_ip,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to record audit log for %s: %s", action, e)

        return response
