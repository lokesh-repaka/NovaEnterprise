"""Middleware package for NovaEnterprise backend."""

from backend.app.middleware.request_context import RequestContextMiddleware

__all__ = ["RequestContextMiddleware"]
