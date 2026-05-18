"""Redis cache for ranked search result pages."""

from __future__ import annotations

import hashlib
import json
import logging

import redis.asyncio as redis

from app.core.config import Settings
from app.core.metrics import record_search_cache

logger = logging.getLogger(__name__)


def search_cache_key(*, query: str, sort: str, status: str | None, domain: str | None, min_confidence: float | None) -> str:
    """Stable cache key from search parameters."""
    payload = json.dumps(
        {
            "q": query.strip().lower(),
            "sort": sort,
            "status": status,
            "domain": domain,
            "min_confidence": min_confidence,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"rmc:search:ranked:{digest}"


async def get_ranked_ids(settings: Settings, key: str) -> list[dict[str, object]] | None:
    """Load cached ranked claim id + score rows."""
    if not settings.search_cache_enabled:
        return None
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        raw = await client.get(key)
        if raw is None:
            record_search_cache(hit=False)
            return None
        data = json.loads(raw)
        if isinstance(data, list):
            record_search_cache(hit=True)
            return data
        record_search_cache(hit=False)
        return None
    finally:
        await client.aclose()


async def set_ranked_ids(
    settings: Settings,
    key: str,
    rows: list[dict[str, object]],
) -> None:
    """Cache ranked results for cursor pagination."""
    if not settings.search_cache_enabled:
        return
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        await client.setex(key, settings.search_cache_ttl_seconds, json.dumps(rows))
    finally:
        await client.aclose()
