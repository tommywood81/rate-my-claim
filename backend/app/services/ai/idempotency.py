"""Redis locks so duplicate Celery enrichment tasks do not run concurrently."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import redis.asyncio as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_LOCK_TTL_SECONDS = 900


@asynccontextmanager
async def enrichment_task_lock(pending_id: UUID | str) -> AsyncIterator[bool]:
    """Acquire a short-lived lock; yield False if another worker holds it."""
    settings = get_settings()
    key = f"rmc:enrich:lock:{pending_id}"
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    acquired = False
    try:
        acquired = bool(await client.set(key, "1", nx=True, ex=_LOCK_TTL_SECONDS))
        if not acquired:
            logger.info("enrichment_lock_skipped", extra={"pending_id": str(pending_id)})
        yield acquired
    finally:
        if acquired:
            await client.delete(key)
        await client.aclose()
