"""Structured logging configuration."""

import logging
import sys
from typing import Any

import json

_STANDARD = {
    "name",
    "msg",
    "args",
    "created",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "exc_info",
    "exc_text",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Serialize log records as single-line JSON with structured extras."""

    def format(self, record: logging.LogRecord) -> str:
        """Build a JSON object from the log record."""
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


class CorrelationIdFilter(logging.Filter):
    """Inject correlation_id from context into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        from app.core.request_context import correlation_id_ctx

        cid = correlation_id_ctx.get()
        if cid:
            record.correlation_id = cid
        return True


def configure_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    """Configure root logger for stdout output."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    handler.addFilter(CorrelationIdFilter())
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
