"""Claim relationship graph and history timeline APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.claims_repository import ClaimRepository
from app.schemas.common import SuccessEnvelope
from app.schemas.graph import ClaimGraphResponse
from app.schemas.timeline import ClaimTimelineResponse
from app.services.graph import ClaimGraphService, ClaimTimelineService

router = APIRouter(tags=["graph"])


@router.get("/claims/{slug}/graph", response_model=SuccessEnvelope[ClaimGraphResponse])
async def claim_graph(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    types: Annotated[str | None, Query(description="Comma-separated relationship types")] = None,
    depth: Annotated[int, Query(ge=1, le=2)] = 1,
    include_evidence_clusters: Annotated[bool, Query()] = True,
) -> SuccessEnvelope[ClaimGraphResponse]:
    """Neighborhood graph for React Flow (filtered by relationship type)."""
    claims = ClaimRepository(db)
    claim = await claims.get_claim_by_slug(slug)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    service = ClaimGraphService(db)
    graph = await service.build_graph(
        focus=claim,
        relationship_types=type_list,
        depth=depth,
        include_evidence_clusters=include_evidence_clusters,
    )
    return SuccessEnvelope(data=graph)


@router.get("/claims/{slug}/timeline", response_model=SuccessEnvelope[ClaimTimelineResponse])
async def claim_timeline(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> SuccessEnvelope[ClaimTimelineResponse]:
    """Unified chronological history for a claim."""
    claims = ClaimRepository(db)
    claim = await claims.get_claim_by_slug(slug)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    service = ClaimTimelineService(db)
    timeline = await service.build_timeline(claim, limit=limit)
    return SuccessEnvelope(data=timeline)
