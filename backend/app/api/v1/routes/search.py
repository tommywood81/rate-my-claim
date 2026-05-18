"""Hybrid search endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_settings_dep
from app.core.config import Settings
from app.db.session import get_db
from app.schemas.common import CursorMeta, SuccessEnvelope
from app.schemas.search import ClaimSearchHitResponse, SearchScoreBreakdown
from app.services.search.claim_search_service import ClaimSearchService, SearchSort
from app.services.search.hybrid_ranking import safe_float

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/claims", response_model=SuccessEnvelope[list[ClaimSearchHitResponse]])
async def search_claims(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    q: Annotated[str, Query(min_length=2, max_length=500)],
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
    cursor: Annotated[str | None, Query()] = None,
    sort: Annotated[SearchSort, Query()] = SearchSort.relevance,
    status: Annotated[str | None, Query(max_length=32)] = None,
    domain: Annotated[str | None, Query(max_length=120)] = None,
    min_confidence: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
) -> SuccessEnvelope[list[ClaimSearchHitResponse]]:
    """Hybrid semantic + lexical search with filters, cursor pagination, and score breakdown."""
    svc = ClaimSearchService(db, settings=settings)
    page = await svc.search(
        query=q,
        limit=limit,
        cursor=cursor,
        sort=sort,
        status=status,
        domain=domain,
        min_confidence=min_confidence,
        budget_scope=f"search:{uuid4()}",
    )
    score_by_id = {s.claim_id: s for s in page.scored}
    data: list[ClaimSearchHitResponse] = []
    for claim in page.claims:
        sc = score_by_id.get(str(claim.id))
        breakdown = SearchScoreBreakdown(
            semantic_similarity=safe_float(sc.components.semantic_similarity if sc else 0.0),
            text_relevance=safe_float(sc.components.text_relevance if sc else 0.0),
            evidence_quality=safe_float(sc.components.evidence_quality if sc else 0.0),
            confidence_score=safe_float(
                sc.components.confidence_score if sc else claim.confidence_score
            ),
            freshness_score=safe_float(
                sc.components.freshness_score if sc else claim.freshness_score
            ),
            relationship_density=safe_float(sc.components.relationship_density if sc else 0.0),
            final_score=safe_float(sc.final_score if sc else 0.0),
        )
        data.append(
            ClaimSearchHitResponse(
                id=claim.id,
                public_slug=claim.public_slug,
                canonical_claim_text=claim.canonical_claim_text,
                status=str(claim.status),
                confidence_score=float(claim.confidence_score),
                evidence_count=int(claim.evidence_count),
                discovery_score=int(claim.discovery_score),
                updated_at=claim.updated_at,
                scores=breakdown,
            )
        )
    return SuccessEnvelope(
        data=data,
        meta=CursorMeta(
            next_cursor=page.next_cursor,
            previous_cursor=None,
            has_more=page.has_more,
        ).model_dump()
        | {"sort": sort.value, "query_key": page.query_key},
    )
