"""Redis-backed login lockout after repeated failures."""

from __future__ import annotations

import logging

import redis.asyncio as redis

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class BruteForceGuard:
    """Track failed logins per account key (username + IP)."""

    def __init__(self, client: redis.Redis, settings: Settings | None = None) -> None:
        """Attach Redis client and settings."""
        self._client = client
        self._settings = settings or get_settings()

    def _key(self, account_key: str) -> str:
        return f"rmc:auth:fail:{account_key[:120]}"

    async def is_locked(self, account_key: str) -> bool:
        """True when failure count reached lockout threshold."""
        raw = await self._client.get(self._key(account_key))
        if raw is None:
            return False
        try:
            count = int(raw)
        except ValueError:
            return False
        return count >= self._settings.auth_brute_force_max_attempts

    async def record_failure(self, account_key: str) -> int:
        """Increment failures; return new count."""
        key = self._key(account_key)
        count = int(await self._client.incr(key))
        if count == 1:
            await self._client.expire(key, self._settings.auth_brute_force_lockout_seconds)
        logger.info("auth_login_failure", extra={"account_key": account_key[:40], "count": count})
        return count

    async def clear_failures(self, account_key: str) -> None:
        """Reset counter after successful login."""
        await self._client.delete(self._key(account_key))
