"""Per-request context for structured logs."""

from __future__ import annotations

import contextvars

correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id",
    default=None,
)
