"""Async retry helper for transient AI provider failures."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE = (
    httpx.HTTPError,
    httpx.TimeoutException,
    ConnectionError,
    TimeoutError,
    OSError,
)


async def with_retries(
    call: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    base_delay_seconds: float,
    operation: str,
) -> T:
    """Invoke ``call`` with exponential backoff on transient errors."""
    attempt = 0
    last_exc: BaseException | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return await call()
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "ai_retry",
                extra={
                    "operation": operation,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "delay_s": delay,
                    "error": str(exc)[:200],
                },
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
