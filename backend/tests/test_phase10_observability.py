"""Phase 10: Prometheus metrics and structured logging."""

from __future__ import annotations

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.logging import JsonFormatter
from app.core.metrics import AI_CACHE, record_ai_cache
from app.main import app


def test_json_formatter_includes_structured_extras() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.provider = "openai"
    record.cache_hit = True
    payload = formatter.format(record)
    assert '"provider": "openai"' in payload
    assert '"cache_hit": true' in payload


def test_prometheus_ai_cache_counter() -> None:
    before = AI_CACHE.labels(result="hit")._value.get()  # type: ignore[attr-defined]
    record_ai_cache(hit=True)
    after = AI_CACHE.labels(result="hit")._value.get()  # type: ignore[attr-defined]
    assert after >= before + 1


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_rmc_series() -> None:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/metrics")
    assert res.status_code == 200
    body = res.text
    assert "rmc_ai_cache_total" in body
    assert "rmc_vector_query_duration_seconds" in body
    assert "rmc_moderation_actions_total" in body
