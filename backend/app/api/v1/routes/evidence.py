"""Evidence retrieval API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.repositories.evidence_artifact_repository import EvidenceArtifactRepository
from app.schemas.common import SuccessEnvelope
from app.schemas.evidence import EvidenceArtifactSummary, EvidenceSearchHitResponse, EvidenceSearchResponse
from app.services.evidence.semantic_retrieval import EvidenceSemanticRetrieval

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/search", response_model=SuccessEnvelope[EvidenceSearchResponse])
async def search_evidence(
    q: Annotated[str, Query(min_length=2, max_length=500)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=50),
) -> SuccessEnvelope[EvidenceSearchResponse]:
    """Semantic search over ingested evidence chunks (provenance preserved)."""
    retrieval = EvidenceSemanticRetrieval(db)
    try:
        hits = await retrieval.search(q, limit=limit, budget_scope=f"evidence_search:{uuid4()}")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return SuccessEnvelope(
        data=EvidenceSearchResponse(
            query=q,
            hits=[
                EvidenceSearchHitResponse(
                    chunk_id=h.chunk_id,
                    chunk_text=h.chunk_text[:2000],
                    similarity=h.similarity,
                    artifact_id=h.artifact_id,
                    artifact_url=h.artifact_url,
                    artifact_title=h.artifact_title,
                    publisher=h.publisher,
                    retrieval_source=h.retrieval_source,
                )
                for h in hits
            ],
        )
    )


@router.get("/artifacts/{artifact_id}", response_model=SuccessEnvelope[EvidenceArtifactSummary])
async def get_evidence_artifact(
    artifact_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessEnvelope[EvidenceArtifactSummary]:
    """Return provenance metadata for a stored evidence artifact."""
    repo = EvidenceArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return SuccessEnvelope(
        data=EvidenceArtifactSummary(
            id=artifact.id,
            url=artifact.url,
            title=artifact.title,
            publisher=artifact.publisher,
            source_type=artifact.source_type,
            retrieval_timestamp=artifact.retrieval_timestamp,
            retrieval_source=artifact.retrieval_source,
            chunk_count=len(artifact.chunks or []),
            citations=artifact.citations,
        )
    )
