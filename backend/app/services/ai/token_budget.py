"""Redis-backed OpenAI token budgets for development safety (daily + per-scope caps)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TokenBudgetExceeded(RuntimeError):  # noqa: N818
    """Raised when a budget check fails before an OpenAI call."""

    def __init__(self, *, kind: str, limit: int, used: int, estimated: int) -> None:
        self.kind = kind
        self.limit = limit
        self.used = used
        self.estimated = estimated
        super().__init__(
            f"openai_token_budget_exceeded:{kind}:used={used}+est={estimated}>limit={limit}"
        )


def utc_date_key() -> str:
    """UTC date string for Redis daily counter key."""
    return datetime.now(tz=UTC).date().isoformat()


def estimate_chat_tokens(system: str, user: str, completion_reserve: int = 4096) -> int:
    """Rough input+output upper bound (~4 chars/token) for pre-flight checks."""
    return max(1, len(system) // 4 + len(user) // 4 + completion_reserve)


def estimate_embedding_tokens(text: str) -> int:
    """Rough token estimate for embedding calls."""
    return max(1, min(len(text), 8192) // 4 + 64)


def _total_tokens_from_object(response: object) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    total = getattr(usage, "total_tokens", None)
    if total is not None:
        return int(total)
    p = getattr(usage, "prompt_tokens", None)
    c = getattr(usage, "completion_tokens", None)
    if p is not None or c is not None:
        return int(p or 0) + int(c or 0)
    return 0


async def assert_budget_allows(
    *,
    settings: Settings,
    scope_key: str,
    estimated_tokens: int,
) -> None:
    """Fail fast before an OpenAI request if counters + estimate would exceed limits."""
    if not settings.openai_enforce_token_budgets:
        return
    day_limit = settings.openai_max_tokens_per_day
    scope_limit = settings.openai_max_tokens_per_claim_scope
    if day_limit <= 0 and scope_limit <= 0:
        return

    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        day_k = f"rmc:openai:tok:day:{utc_date_key()}"
        scope_k = f"rmc:openai:tok:scope:{scope_key[:180]}"
        day_used = int(await client.get(day_k) or 0)
        scope_used = int(await client.get(scope_k) or 0)

        if day_limit > 0 and day_used + estimated_tokens > day_limit:
            raise TokenBudgetExceeded(
                kind="daily",
                limit=day_limit,
                used=day_used,
                estimated=estimated_tokens,
            )
        if scope_limit > 0 and scope_used + estimated_tokens > scope_limit:
            raise TokenBudgetExceeded(
                kind="per_claim_scope",
                limit=scope_limit,
                used=scope_used,
                estimated=estimated_tokens,
            )
    finally:
        await client.aclose()


async def record_token_usage(*, scope_key: str, actual_tokens: int) -> None:
    """Increment Redis counters after a successful OpenAI response."""
    settings = get_settings()
    if not settings.openai_enforce_token_budgets:
        return
    if actual_tokens <= 0:
        return
    day_limit = settings.openai_max_tokens_per_day
    scope_limit = settings.openai_max_tokens_per_claim_scope
    if day_limit <= 0 and scope_limit <= 0:
        return

    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        day_k = f"rmc:openai:tok:day:{utc_date_key()}"
        scope_k = f"rmc:openai:tok:scope:{scope_key[:180]}"
        pipe = client.pipeline(transaction=True)
        pipe.incrby(day_k, actual_tokens)
        pipe.expire(day_k, 172800)
        pipe.incrby(scope_k, actual_tokens)
        pipe.expire(scope_k, 2592000)
        await pipe.execute()
        logger.info(
            "openai_token_usage_recorded",
            extra={"scope": scope_key[:80], "tokens": actual_tokens},
        )
    finally:
        await client.aclose()


async def budget_chat_call(
    *,
    settings: Settings,
    scope_key: str,
    system: str,
    user: str,
    completion_reserve: int,
    call,
):
    """Pre-check budget, run async OpenAI chat call, record usage from response."""
    est = estimate_chat_tokens(system, user, completion_reserve=completion_reserve)
    await assert_budget_allows(settings=settings, scope_key=scope_key, estimated_tokens=est)
    response = await call()
    actual = _total_tokens_from_object(response)
    if actual <= 0:
        actual = est
    await record_token_usage(scope_key=scope_key, actual_tokens=actual)
    return response


async def budget_embedding_call(
    *,
    settings: Settings,
    scope_key: str,
    text: str,
    call,
):
    """Pre-check budget, run embedding call, record usage."""
    est = estimate_embedding_tokens(text)
    await assert_budget_allows(settings=settings, scope_key=scope_key, estimated_tokens=est)
    response = await call()
    actual = _total_tokens_from_object(response)
    if actual <= 0:
        actual = est
    await record_token_usage(scope_key=scope_key, actual_tokens=actual)
    return response
