"""Redis cache for idempotent AI operation results."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def build_cache_key(provider: str, operation: str, payload: str) -> str:
    """Stable Redis key from provider, operation, and serialized inputs."""
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"rmc:ai:cache:{provider}:{operation}:{digest}"


def serialize_payload(*parts: Any) -> str:
    """JSON-serialize cache key material."""
    return json.dumps(parts, sort_keys=True, default=str)


async def get_cached(settings: Settings, key: str) -> Any | None:
    """Return deserialized value or None."""
    if not settings.ai_cache_enabled:
        return None
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    finally:
        await client.aclose()


async def set_cached(settings: Settings, key: str, value: Any) -> None:
    """Store JSON-serializable value with TTL."""
    if not settings.ai_cache_enabled:
        return
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        await client.setex(key, settings.ai_cache_ttl_seconds, json.dumps(value, default=str))
    finally:
        await client.aclose()


def pack_embedding(result: tuple[list[float], str]) -> dict[str, Any]:
    """Cache-friendly embedding tuple."""
    vec, model = result
    return {"vec": vec, "model": model}


def unpack_embedding(data: dict[str, Any]) -> tuple[list[float], str]:
    """Restore embedding tuple from cache."""
    return list(data["vec"]), str(data["model"])
