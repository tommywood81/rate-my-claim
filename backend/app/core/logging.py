"""Structured logging configuration."""

import logging
import sys
from typing import Any

import json


class JsonFormatter(logging.Formatter):
    """Serialize log records as single-line JSON."""

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
        if hasattr(record, "correlation_id"):
            payload["correlation_id"] = getattr(record, "correlation_id", None)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger for JSON stdout output."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
