"""Hybrid search endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_settings_dep
from app.core.config import Settings
from app.db.session import get_db
from app.repositories.claims_repository import HybridSearchRepository
from app.schemas.claims import ClaimListItemResponse
from app.schemas.common import SuccessEnvelope
from app.services.ai.factory import get_ai_provider

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/claims", response_model=SuccessEnvelope[list[ClaimListItemResponse]])
async def search_claims(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    q: Annotated[str, Query(min_length=2, max_length=500)],
    limit: Annotated[int, Query(ge=1, le=30)] = 15,
) -> SuccessEnvelope[list[ClaimListItemResponse]]:
    """Hybrid semantic + lexical search over approved claims."""
    provider = get_ai_provider()
    vec, _ = await provider.generate_embedding(q)
    repo = HybridSearchRepository(db)
    rows = await repo.hybrid_search(query_text=q, query_embedding=vec, limit=limit, settings=settings)
    data = [ClaimListItemResponse.model_validate(c) for c, _ in rows]
    return SuccessEnvelope(data=data, meta={"has_more": False})
