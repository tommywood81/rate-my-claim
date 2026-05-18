"""Estimated USD cost tracking for OpenAI usage (Redis counters)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from app.core.config import Settings, get_settings
from app.services.ai.token_budget import utc_date_key

logger = logging.getLogger(__name__)

# USD per 1M tokens (approximate list prices; override via env if needed later)
_MODEL_COST_PER_1M: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
}


def estimate_cost_usd(
    model: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> float:
    """Rough USD cost from token counts and model id."""
    rates = _MODEL_COST_PER_1M.get(model, _MODEL_COST_PER_1M["gpt-4o-mini"])
    in_cost = (prompt_tokens / 1_000_000) * rates.get("input", 0.0)
    out_cost = (completion_tokens / 1_000_000) * rates.get("output", 0.0)
    return round(in_cost + out_cost, 8)


def _usage_tokens(response: object) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    p = int(getattr(usage, "prompt_tokens", 0) or 0)
    c = int(getattr(usage, "completion_tokens", 0) or 0)
    return p, c


async def record_cost_usd(
    *,
    scope_key: str,
    model: str,
    cost_usd: float,
    settings: Settings | None = None,
) -> None:
    """Increment daily and per-scope cost counters in Redis."""
    cfg = settings or get_settings()
    if not cfg.ai_track_cost_usd or cost_usd <= 0:
        return
    client = redis.from_url(str(cfg.redis_url), decode_responses=True)
    try:
        day_k = f"rmc:openai:cost:day:{utc_date_key()}"
        scope_k = f"rmc:openai:cost:scope:{scope_key[:180]}"
        pipe = client.pipeline(transaction=True)
        pipe.incrbyfloat(day_k, cost_usd)
        pipe.expire(day_k, 172800)
        pipe.incrbyfloat(scope_k, cost_usd)
        pipe.expire(scope_k, 2592000)
        await pipe.execute()
        logger.info(
            "openai_cost_recorded",
            extra={"scope": scope_key[:80], "model": model, "cost_usd": cost_usd},
        )
    finally:
        await client.aclose()


async def record_cost_from_response(
    *,
    scope_key: str,
    model: str,
    response: object,
    settings: Settings | None = None,
) -> float:
    """Estimate and record cost from an OpenAI response usage block."""
    prompt_t, completion_t = _usage_tokens(response)
    cost = estimate_cost_usd(model, prompt_tokens=prompt_t, completion_tokens=completion_t)
    await record_cost_usd(scope_key=scope_key, model=model, cost_usd=cost, settings=settings)
    return cost
