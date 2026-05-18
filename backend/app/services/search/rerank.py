"""Optional reranking hooks after hybrid fusion."""

from __future__ import annotations

from typing import Protocol

from app.models.claim import Claim
from app.services.search.hybrid_ranking import ScoredClaim


class SearchReranker(Protocol):
    """Extension point for LLM or cross-encoder reranking."""

    async def rerank(
        self,
        query: str,
        claims: list[Claim],
        scored: list[ScoredClaim],
    ) -> list[ScoredClaim]:
        """Return reordered scored claims."""


class PassthroughReranker:
    """Default no-op reranker."""

    async def rerank(
        self,
        query: str,
        claims: list[Claim],
        scored: list[ScoredClaim],
    ) -> list[ScoredClaim]:
        return scored
