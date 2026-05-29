"""Public claim embedding atlas (3D semantic space)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.repositories.claims_repository import ClaimRepository
from app.schemas.atlas import ClaimAtlasPointResponse, ClaimAtlasResponse
from app.schemas.common import SuccessEnvelope
from app.services.claims.embedding_atlas import (
    build_atlas_projection,
    enrich_rows_with_truth_labels,
    rows_from_claims,
)

router = APIRouter(tags=["atlas"])


@router.get("/atlas/claims", response_model=SuccessEnvelope[ClaimAtlasResponse])
async def claim_embedding_atlas(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    limit: Annotated[int | None, Query(ge=10, le=800)] = None,
) -> SuccessEnvelope[ClaimAtlasResponse]:
    """
    Project indexed claim embeddings into 3D for interactive exploration.

    Uses PCA on stored vectors; the corpus grows as more claims receive embeddings.
    """
    cap = limit if limit is not None else settings.atlas_max_claims
    repo = ClaimRepository(db)
    claims = await repo.list_claims_with_embeddings(limit=cap)
    total_indexed = await repo.count_claims_with_embeddings()
    rows = await enrich_rows_with_truth_labels(db, rows_from_claims(claims))
    projection = build_atlas_projection(rows)

    data = ClaimAtlasResponse(
        points=[ClaimAtlasPointResponse.model_validate(asdict(p)) for p in projection.points],
        method=projection.method,
        embedding_dimensions=projection.embedding_dimensions,
        total_indexed=total_indexed,
        projected_count=projection.projected_count,
        computed_at=projection.computed_at,
    )
    return SuccessEnvelope(
        data=data,
        meta={
            "display_limit": cap,
            "truncated": total_indexed > projection.projected_count,
        },
    )
