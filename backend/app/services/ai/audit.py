"""Structured audit logging for AI provider calls."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def log_ai_call(
    *,
    provider: str,
    operation: str,
    scope_key: str,
    model: str | None,
    duration_ms: float,
    cache_hit: bool,
    success: bool,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a single structured log line for observability and audit trails."""
    payload: dict[str, Any] = {
        "provider": provider,
        "operation": operation,
        "scope": scope_key[:120],
        "model": model,
        "duration_ms": round(duration_ms, 2),
        "cache_hit": cache_hit,
        "success": success,
    }
    if error:
        payload["error"] = error[:500]
    if extra:
        payload.update(extra)
    if success:
        logger.info("ai_call", extra=payload)
    else:
        logger.warning("ai_call_failed", extra=payload)


class AICallTimer:
    """Context helper for timing provider operations."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0
