"""Prometheus metrics for production observability."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram, Info

# AI usage
AI_TOKENS = Counter(
    "rmc_ai_tokens_total",
    "Total AI tokens consumed",
    ["provider", "operation", "model"],
)
AI_COST_USD = Counter(
    "rmc_ai_cost_usd_total",
    "Estimated AI spend in USD",
    ["provider", "model"],
)
AI_CACHE = Counter(
    "rmc_ai_cache_total",
    "AI Redis cache lookups",
    ["result"],
)
AI_CALLS = Counter(
    "rmc_ai_calls_total",
    "AI provider operations",
    ["provider", "operation", "status"],
)
AI_DURATION = Histogram(
    "rmc_ai_call_duration_seconds",
    "AI call latency",
    ["provider", "operation"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 60.0),
)

# Search
SEARCH_CACHE = Counter(
    "rmc_search_cache_total",
    "Hybrid search ranked-result cache",
    ["result"],
)
VECTOR_QUERY_DURATION = Histogram(
    "rmc_vector_query_duration_seconds",
    "pgvector / hybrid retrieval latency",
    ["operation"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# API errors (complements instrumentator HTTP metrics)
API_ERRORS = Counter(
    "rmc_api_errors_total",
    "Application-level API errors",
    ["code"],
)

# Moderation
MODERATION_ACTIONS = Counter(
    "rmc_moderation_actions_total",
    "Moderator actions applied",
    ["action_type"],
)

# Celery
CELERY_QUEUE_DEPTH = Gauge(
    "rmc_celery_queue_depth",
    "Approximate Celery broker queue length",
    ["queue"],
)
CELERY_WORKERS = Gauge(
    "rmc_celery_workers_online",
    "Celery workers responding to inspect",
)

APP_INFO = Info("rmc_app", "Application build metadata")


def set_app_info(*, version: str, environment: str) -> None:
    """Expose static labels on /metrics."""
    APP_INFO.info({"version": version, "environment": environment})


def record_ai_cache(*, hit: bool) -> None:
    AI_CACHE.labels(result="hit" if hit else "miss").inc()


def record_search_cache(*, hit: bool) -> None:
    SEARCH_CACHE.labels(result="hit" if hit else "miss").inc()


def record_ai_call(
    *,
    provider: str,
    operation: str,
    duration_seconds: float,
    success: bool,
    cache_hit: bool,
) -> None:
    status = "success" if success else "error"
    AI_CALLS.labels(provider=provider, operation=operation, status=status).inc()
    AI_DURATION.labels(provider=provider, operation=operation).observe(duration_seconds)
    record_ai_cache(hit=cache_hit)


def record_ai_tokens(*, provider: str, operation: str, model: str, tokens: int) -> None:
    if tokens > 0:
        AI_TOKENS.labels(provider=provider, operation=operation, model=model).inc(tokens)


def record_ai_cost(*, provider: str, model: str, cost_usd: float) -> None:
    if cost_usd > 0:
        AI_COST_USD.labels(provider=provider, model=model).inc(cost_usd)


def record_moderation(action_type: str) -> None:
    MODERATION_ACTIONS.labels(action_type=action_type).inc()


def record_api_error(code: str) -> None:
    API_ERRORS.labels(code=code).inc()


@contextmanager
def observe_vector_query(operation: str) -> Generator[None, None, None]:
    """Time a vector/hybrid DB query."""
    start = time.perf_counter()
    try:
        yield
    finally:
        VECTOR_QUERY_DURATION.labels(operation=operation).observe(time.perf_counter() - start)
