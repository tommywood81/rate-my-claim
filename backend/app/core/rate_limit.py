"""SlowAPI limiter wired to Redis."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def build_limiter() -> Limiter:
    """Create limiter using Redis when configured."""
    settings = get_settings()
    storage = str(settings.redis_url)
    return Limiter(key_func=get_remote_address, storage_uri=storage, default_limits=[])


limiter = build_limiter()
