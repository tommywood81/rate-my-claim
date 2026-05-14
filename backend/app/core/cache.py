"""Redis cache facade for AI and retrieval results."""

import json
from typing import Any, TypeVar

import redis.asyncio as redis

from app.core.config import get_settings

T = TypeVar("T")


class CacheService:
    """Async Redis key-value cache with JSON serialization."""

    def __init__(self, client: redis.Redis) -> None:
        """Store the Redis client."""
        self._client = client

    async def get_json(self, key: str) -> Any | None:
        """Return deserialized JSON or None if missing."""
        raw = await self._client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Serialize value to JSON and set with TTL."""
        await self._client.setex(key, ttl_seconds, json.dumps(value, default=str))


async def get_redis() -> redis.Redis:
    """Build a Redis client from settings."""
    settings = get_settings()
    return redis.from_url(str(settings.redis_url), decode_responses=True)
