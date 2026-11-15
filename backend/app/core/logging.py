"""Structured JSON logging module for NovaEnterprise.

Provides JSON-formatted logs with request-id context propagation across async tasks.
"""

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict, Optional, TextIO

STANDARD_LOG_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}

# Context variable to hold the request_id across coroutines / threads
_request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Retrieve the current request ID from context."""
    return _request_id_ctx_var.get()


def set_request_id(request_id: Optional[str]) -> None:
    """Set the current request ID in context."""
    _request_id_ctx_var.set(request_id)


class JSONFormatter(logging.Formatter):
    """Custom formatter emitting single-line JSON with context and extra attributes."""

    def format(self, record: logging.LogRecord) -> str:
        # Resolve message
        message = record.getMessage()

        # Base log payload
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }

        # Request ID propagation (either from record attribute or contextvar)
        req_id = getattr(record, "request_id", None) or get_request_id()
        if req_id is not None:
            log_payload["request_id"] = req_id

        # Exception formatting
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_payload["exception"] = record.exc_text

        if record.stack_info:
            log_payload["stack_info"] = self.formatStack(record.stack_info)

        # Include custom extra fields
        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_ATTRS and key not in log_payload:
                try:
                    # Test JSON serializability
                    json.dumps(value)
                    log_payload[key] = value
                except (TypeError, OverflowError):
                    log_payload[key] = str(value)

        return json.dumps(log_payload, default=str)


def setup_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    stream: Optional[TextIO] = None,
) -> None:
    """Configure root logger with structured JSON formatting or standard text."""
    if log_level is None or log_format is None:
        try:
            from backend.app.core.config import get_settings

            settings = get_settings()
            log_level = log_level or settings.log_level
            log_format = log_format or settings.log_format
        except Exception:
            log_level = log_level or "INFO"
            log_format = log_format or "json"

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    target_stream = stream or sys.stdout

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(target_stream)
    handler.setLevel(numeric_level)

    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
        )

    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the specified name."""
    return logging.getLogger(name)
