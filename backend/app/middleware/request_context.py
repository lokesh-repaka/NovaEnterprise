"""Request context and tracking middleware (N5).

Generates or preserves X-Request-ID on all incoming requests, binds request_id
to contextvars for structured JSON log correlation, and ensures X-Request-ID
is present on every response.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.logging import set_request_id

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware to propagate and correlate X-Request-ID across the request lifecycle."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Check incoming headers for an existing request ID (case-insensitive)
        incoming_id = request.headers.get("x-request-id") or request.headers.get(
            REQUEST_ID_HEADER
        )

        if incoming_id and incoming_id.strip():
            request_id = incoming_id.strip()
        else:
            request_id = str(uuid.uuid4())

        # Store in request state for convenient route-handler access
        request.state.request_id = request_id

        # Bind to contextvar for structured logging correlation
        set_request_id(request_id)

        try:
            response = await call_next(request)
            # Ensure response contains X-Request-ID header
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            # Clean up contextvar to prevent cross-task leakage
            set_request_id(None)
