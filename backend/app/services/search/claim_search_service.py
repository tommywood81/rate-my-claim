"""Production hybrid claim search with caching, filters, and cursor pages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.claim import Claim
from app.repositories.search_repository import SearchRepository
from app.services.ai.factory import get_ai_provider
from app.services.search.cache import get_ranked_ids, search_cache_key, set_ranked_ids
from app.services.search.hybrid_ranking import RankComponents, ScoredClaim, build_scored_claims, safe_float
from app.services.search.rerank import PassthroughReranker, SearchReranker
from app.utils.search_cursor import SearchPageCursor, decode_search_cursor, encode_search_cursor

logger = logging.getLogger(__name__)

class SearchSort(str, Enum):
    """Supported search sort modes."""

    relevance = "relevance"
    confidence = "confidence"
    freshness = "freshness"
    updated = "updated"


@dataclass
class SearchPageResult:
    """One page of search hits."""

    claims: list[Claim]
    scored: list[ScoredClaim]
    next_cursor: str | None
    has_more: bool
    query_key: str


class ClaimSearchService:
    """Orchestrate embedding, hybrid ranking, cache, rerank, and pagination."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        reranker: SearchReranker | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repo = SearchRepository(session)
        self._reranker = reranker or PassthroughReranker()

    async def search(
        self,
        *,
        query: str,
        limit: int = 15,
        cursor: str | None = None,
        sort: SearchSort = SearchSort.relevance,
        status: str | None = None,
        domain: str | None = None,
        min_confidence: float | None = None,
        budget_scope: str = "search",
    ) -> SearchPageResult:
        """Run hybrid search with stable cursor pagination."""
        q = query.strip()
        if len(q) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query_too_short")

        cache_key = search_cache_key(
            query=q,
            sort=sort.value,
            status=status,
            domain=domain,
            min_confidence=min_confidence,
        )
        page_cursor = decode_search_cursor(cursor)
        if page_cursor and page_cursor.query_key != cache_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cursor_mismatch")

        ranked = await get_ranked_ids(self._settings, cache_key)
        if ranked is None:
            provider = get_ai_provider(budget_scope=budget_scope)
            vec, _ = await provider.generate_embedding(q)
            raw = await self._repo.fetch_hybrid_candidates(
                query_text=q,
                query_embedding=vec,
                candidate_limit=self._settings.search_max_candidates,
                status=status,
                domain=domain,
                min_confidence=min_confidence,
            )
            scored = build_scored_claims(raw, self._settings)
            claim_map = await self._repo.load_claims_by_ids([UUID(s.claim_id) for s in scored])
            claims_ordered = [claim_map[UUID(s.claim_id)] for s in scored if UUID(s.claim_id) in claim_map]
            scored = await self._reranker.rerank(q, claims_ordered, scored)
            scored = self._apply_sort(scored, claim_map, sort)
            ranked = [
                {
                    "id": s.claim_id,
                    "score": s.final_score,
                    "components": {
                        "semantic_similarity": s.components.semantic_similarity,
                        "text_relevance": s.components.text_relevance,
                        "evidence_quality": s.components.evidence_quality,
                        "confidence_score": s.components.confidence_score,
                        "freshness_score": s.components.freshness_score,
                        "relationship_density": s.components.relationship_density,
                    },
                }
                for s in scored
            ]
            await set_ranked_ids(self._settings, cache_key, ranked)
            logger.info("search_ranked_cache_miss", extra={"query_len": len(q), "hits": len(ranked)})

        offset = page_cursor.offset if page_cursor else 0
        page_rows = ranked[offset : offset + limit + 1]
        has_more = len(page_rows) > limit
        page_rows = page_rows[:limit]
        if not page_rows:
            return SearchPageResult(
                claims=[],
                scored=[],
                next_cursor=None,
                has_more=False,
                query_key=cache_key,
            )

        ids = [UUID(row["id"]) for row in page_rows]
        claim_map = await self._repo.load_claims_by_ids(ids)
        claims = [claim_map[i] for i in ids if i in claim_map]
        scored_page: list[ScoredClaim] = []
        for row in page_rows:
            cid = UUID(str(row["id"]))
            if cid not in claim_map:
                continue
            comp_raw = row.get("components") or {}
            if isinstance(comp_raw, dict):
                components = RankComponents(
                    semantic_similarity=float(comp_raw.get("semantic_similarity", 0)),
                    text_relevance=float(comp_raw.get("text_relevance", 0)),
                    evidence_quality=float(comp_raw.get("evidence_quality", 0)),
                    confidence_score=float(comp_raw.get("confidence_score", 0)),
                    freshness_score=float(comp_raw.get("freshness_score", 0)),
                    relationship_density=float(comp_raw.get("relationship_density", 0)),
                )
            else:
                c = claim_map[cid]
                components = RankComponents(
                    semantic_similarity=0.0,
                    text_relevance=0.0,
                    evidence_quality=min(1.0, float(c.evidence_count) / 6.0),
                    confidence_score=float(c.confidence_score),
                    freshness_score=float(c.freshness_score),
                    relationship_density=0.0,
                )
            scored_page.append(
                ScoredClaim(
                    claim_id=str(cid),
                    final_score=safe_float(row.get("score")),
                    components=components,
                )
            )

        next_cursor = None
        if has_more:
            next_cursor = encode_search_cursor(
                SearchPageCursor(offset=offset + limit, query_key=cache_key)
            )

        return SearchPageResult(
            claims=claims,
            scored=scored_page,
            next_cursor=next_cursor,
            has_more=has_more,
            query_key=cache_key,
        )

    def _apply_sort(
        self,
        scored: list[ScoredClaim],
        claim_map: dict[UUID, Claim],
        sort: SearchSort,
    ) -> list[ScoredClaim]:
        """Sort scored claims by requested mode."""
        if sort == SearchSort.relevance:
            return sorted(scored, key=lambda s: s.final_score, reverse=True)
        if sort == SearchSort.confidence:
            return sorted(
                scored,
                key=lambda s: claim_map[UUID(s.claim_id)].confidence_score
                if UUID(s.claim_id) in claim_map
                else 0.0,
                reverse=True,
            )
        if sort == SearchSort.freshness:
            return sorted(
                scored,
                key=lambda s: claim_map[UUID(s.claim_id)].freshness_score
                if UUID(s.claim_id) in claim_map
                else 0.0,
                reverse=True,
            )
        if sort == SearchSort.updated:
            return sorted(
                scored,
                key=lambda s: claim_map[UUID(s.claim_id)].updated_at
                if UUID(s.claim_id) in claim_map
                else 0,
                reverse=True,
            )
        return scored
