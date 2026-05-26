"""Cross-cutting cache, retry, and audit wrapper for any BaseAIProvider."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.config import Settings, get_settings
from app.services.ai import audit, cache, retry
from app.services.ai.routing import model_for_operation
from app.services.ai.providers.base import BaseAIProvider

T = TypeVar("T")


class InstrumentedAIProvider(BaseAIProvider):
    """Decorator provider adding Redis cache, retries, and structured audit logs."""

    def __init__(
        self,
        inner: BaseAIProvider,
        *,
        scope_key: str,
        settings: Settings | None = None,
    ) -> None:
        self._inner = inner
        self._scope = scope_key
        self._settings = settings or get_settings()
        self.name = inner.name

    async def _execute(
        self,
        operation: str,
        call: Callable[[], Awaitable[T]],
        *,
        cache_payload: str,
        pack: Callable[[T], Any] | None = None,
        unpack: Callable[[Any], T] | None = None,
    ) -> T:
        key = cache.build_cache_key(self.name, operation, cache_payload)
        timer = audit.AICallTimer()
        model = model_for_operation(self._settings, operation)

        if self._settings.ai_cache_enabled:
            hit = await cache.get_cached(self._settings, key)
            if hit is not None:
                audit.log_ai_call(
                    provider=self.name,
                    operation=operation,
                    scope_key=self._scope,
                    model=model,
                    duration_ms=timer.elapsed_ms,
                    cache_hit=True,
                    success=True,
                )
                if unpack is not None:
                    return unpack(hit)
                return hit  # type: ignore[return-value]

        try:
            result = await retry.with_retries(
                call,
                max_attempts=self._settings.ai_retry_max_attempts,
                base_delay_seconds=self._settings.ai_retry_base_delay_seconds,
                operation=operation,
            )
        except Exception as exc:
            audit.log_ai_call(
                provider=self.name,
                operation=operation,
                scope_key=self._scope,
                model=model,
                duration_ms=timer.elapsed_ms,
                cache_hit=False,
                success=False,
                error=str(exc),
            )
            raise

        if self._settings.ai_cache_enabled:
            stored = pack(result) if pack is not None else result
            await cache.set_cached(self._settings, key, stored)

        audit.log_ai_call(
            provider=self.name,
            operation=operation,
            scope_key=self._scope,
            model=model,
            duration_ms=timer.elapsed_ms,
            cache_hit=False,
            success=True,
        )
        return result

    async def generate_embedding(self, text: str) -> tuple[list[float], str]:
        return await self._execute(
            "generate_embedding",
            lambda: self._inner.generate_embedding(text),
            cache_payload=cache.serialize_payload(text),
            pack=cache.pack_embedding,
            unpack=cache.unpack_embedding,
        )

    async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
        return await self._execute(
            "canonicalize_claim",
            lambda: self._inner.canonicalize_claim(raw_text),
            cache_payload=cache.serialize_payload(raw_text),
        )

    async def summarize_evidence(self, context: str) -> str:
        return await self._execute(
            "summarize_evidence",
            lambda: self._inner.summarize_evidence(context),
            cache_payload=cache.serialize_payload(context),
        )

    async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
        return await self._execute(
            "classify_stance",
            lambda: self._inner.classify_stance(claim, evidence_excerpt),
            cache_payload=cache.serialize_payload(claim, evidence_excerpt),
        )

    async def detect_duplicates(self, claim: str, candidates: list[str]) -> list[int]:
        return await self._execute(
            "detect_duplicates",
            lambda: self._inner.detect_duplicates(claim, candidates),
            cache_payload=cache.serialize_payload(claim, candidates),
        )

    async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
        return await self._execute(
            "analyze_contradictions",
            lambda: self._inner.analyze_contradictions(claim, evidence_blocks),
            cache_payload=cache.serialize_payload(claim, evidence_blocks),
        )

    async def generate_confidence_analysis(
        self,
        claim: str,
        evidence_digest: str,
    ) -> dict[str, Any]:
        return await self._execute(
            "generate_confidence_analysis",
            lambda: self._inner.generate_confidence_analysis(claim, evidence_digest),
            cache_payload=cache.serialize_payload(claim, evidence_digest),
        )

    async def structured_verdict(
        self,
        claim: str,
        retrieved_context: str,
    ) -> dict[str, Any]:
        return await self._execute(
            "structured_verdict",
            lambda: self._inner.structured_verdict(claim, retrieved_context),
            cache_payload=cache.serialize_payload(claim, retrieved_context),
        )

    async def generate_combined_assessment(
        self,
        claim: str,
        evidence_context: str,
        evidence_digest: str,
    ) -> dict[str, Any]:
        """Combined assessment when the inner provider implements it."""
        inner_fn = getattr(self._inner, "generate_combined_assessment", None)
        if inner_fn is None:
            scores = await self.generate_confidence_analysis(claim, evidence_digest)
            verdict = await self.structured_verdict(claim, evidence_context)
            merged = dict(scores)
            merged.update(verdict)
            return merged
        return await self._execute(
            "generate_combined_assessment",
            lambda: inner_fn(claim, evidence_context, evidence_digest),
            cache_payload=cache.serialize_payload(claim, evidence_context, evidence_digest),
        )
