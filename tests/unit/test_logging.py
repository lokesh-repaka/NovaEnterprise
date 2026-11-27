"""Unit tests for JSON logging and request-id propagation (P1-1).

Proves: N1 (offline runtime logging),
        N5 (request-id propagation to logs).
"""

import json
import logging
from io import StringIO

from backend.app.core.logging import (
    JSONFormatter,
    get_logger,
    get_request_id,
    set_request_id,
    setup_logging,
)


def test_json_formatter_basic():
    """Verify JSONFormatter outputs valid JSON with standard fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message with %s",
        args=("params",),
        exc_info=None,
    )

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test message with params"
    assert "timestamp" in parsed


def test_json_formatter_with_request_id_context():
    """Verify request_id from contextvars is included in JSON log output."""
    formatter = JSONFormatter()

    set_request_id("req-abc-123")
    assert get_request_id() == "req-abc-123"

    record = logging.LogRecord(
        name="test_logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=20,
        msg="Warning event",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["request_id"] == "req-abc-123"

    # Clear request_id
    set_request_id(None)
    assert get_request_id() is None

    record_no_req = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=25,
        msg="Another event",
        args=(),
        exc_info=None,
    )

    output_no_req = formatter.format(record_no_req)
    parsed_no_req = json.loads(output_no_req)
    assert parsed_no_req.get("request_id") is None


def test_json_formatter_extra_fields():
    """Verify extra dictionary attributes appear as top-level fields in JSON."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=30,
        msg="User action logged",
        args=(),
        exc_info=None,
    )
    record.user_id = "usr-001"
    record.action = "document_upload"

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["user_id"] == "usr-001"
    assert parsed["action"] == "document_upload"


def test_json_formatter_exception():
    """Verify exceptions are captured and formatted in the JSON output."""
    formatter = JSONFormatter()
    try:
        raise ValueError("Invalid calculation")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=40,
        msg="Operation failed",
        args=(),
        exc_info=exc_info,
    )

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "ERROR"
    assert "exception" in parsed
    assert "ValueError: Invalid calculation" in parsed["exception"]


def test_setup_logging_and_get_logger():
    """Verify setup_logging configures root/logger with JSONFormatter."""
    stream = StringIO()
    setup_logging(log_level="DEBUG", log_format="json", stream=stream)

    logger = get_logger("app.test")
    logger.debug("Debug event dispatched", extra={"custom_tag": "tag-value"})

    output = stream.getvalue().strip()
    assert output != ""
    parsed = json.loads(output.splitlines()[-1])

    assert parsed["level"] == "DEBUG"
    assert parsed["logger"] == "app.test"
    assert parsed["message"] == "Debug event dispatched"
    assert parsed["custom_tag"] == "tag-value"
