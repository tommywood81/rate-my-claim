"""Phase 5: provider registry, routing, cache, retry, and instrumentation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.ai.cache import build_cache_key, pack_embedding, serialize_payload, unpack_embedding
from app.services.ai.cost_tracking import estimate_cost_usd
from app.services.ai.instrumented_provider import InstrumentedAIProvider
from app.services.ai.registry import create_provider, list_providers
from app.services.ai.retry import with_retries
from app.services.ai.routing import TaskTier, model_for_operation, tier_for_operation
from app.services.ai.providers.base import BaseAIProvider


class CountingProvider(BaseAIProvider):
    """Minimal provider that counts embedding invocations."""

    name = "counting"

    def __init__(self) -> None:
        self.embedding_calls = 0

    async def generate_embedding(self, text: str) -> tuple[list[float], str]:
        self.embedding_calls += 1
        return [0.1, 0.2], "count-emb"

    async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
        return {"canonical_text": raw_text}

    async def summarize_evidence(self, context: str) -> str:
        return "summary"

    async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
        return "contextualizes"

    async def detect_duplicates(self, claim: str, candidates: list[str]) -> list[int]:
        return []

    async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
        return "none"

    async def generate_confidence_analysis(
        self,
        claim: str,
        evidence_digest: str,
    ) -> dict[str, Any]:
        return {"aggregate": 0.5}

    async def structured_verdict(self, claim: str, retrieved_context: str) -> dict[str, Any]:
        return {"verdict_summary": "ok"}


def test_list_providers() -> None:
    assert set(list_providers()) == {"openai", "ollama"}


def test_model_routing_tiers() -> None:
    assert tier_for_operation("canonicalize_claim") == TaskTier.cheap
    assert tier_for_operation("structured_verdict") == TaskTier.reasoning


def test_model_for_operation_uses_settings() -> None:
    settings = Settings.model_construct(
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        ai_model_cheap="cheap-model",
        ai_model_reasoning="reasoning-model",
    )
    assert model_for_operation(settings, "classify_stance") == "cheap-model"
    assert model_for_operation(settings, "analyze_contradictions") == "reasoning-model"


def test_estimate_cost_usd() -> None:
    cost = estimate_cost_usd("gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0


@pytest.mark.asyncio
async def test_retry_succeeds_after_transient_failure() -> None:
    attempts = 0

    async def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("transient")
        return "ok"

    result = await with_retries(
        flaky,
        max_attempts=3,
        base_delay_seconds=0.01,
        operation="test",
    )
    assert result == "ok"
    assert attempts == 2


@pytest.mark.asyncio
async def test_instrumented_provider_caches_embedding() -> None:
    inner = CountingProvider()
    settings = Settings.model_construct(
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        ai_cache_enabled=True,
        ai_retry_max_attempts=1,
    )
    provider = InstrumentedAIProvider(inner, scope_key="test", settings=settings)
    key = build_cache_key("counting", "generate_embedding", serialize_payload("hello"))

    with (
        patch("app.services.ai.instrumented_provider.cache.get_cached", new_callable=AsyncMock) as get_m,
        patch("app.services.ai.instrumented_provider.cache.set_cached", new_callable=AsyncMock) as set_m,
    ):
        get_m.side_effect = [None, pack_embedding(([0.1, 0.2], "count-emb"))]
        await provider.generate_embedding("hello")
        await provider.generate_embedding("hello")

    assert inner.embedding_calls == 1
    assert set_m.await_count == 1
    get_m.assert_awaited()
    assert get_m.await_args_list[0].args[1] == key


@pytest.mark.asyncio
async def test_create_provider_openai_requires_key() -> None:
    settings = Settings.model_construct(
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        openai_api_key=None,
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        create_provider("openai", settings=settings)


@pytest.mark.asyncio
async def test_factory_wraps_with_instrumentation() -> None:
    settings = Settings.model_construct(
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        ai_provider="openai",
        openai_api_key="sk-test",
        ai_cache_enabled=False,
    )
    mock_inner = CountingProvider()
    with (
        patch("app.services.ai.factory.get_settings", return_value=settings),
        patch("app.services.ai.factory.create_provider", return_value=mock_inner),
    ):
        from app.services.ai.factory import get_ai_provider

        provider = get_ai_provider(budget_scope="unit")
    assert isinstance(provider, InstrumentedAIProvider)
    assert provider.name == "counting"


def test_pack_unpack_embedding_roundtrip() -> None:
    original = ([1.0, 2.0], "emb-v1")
    restored = unpack_embedding(pack_embedding(original))
    assert restored == original
