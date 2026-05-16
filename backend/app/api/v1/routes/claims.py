"""Public claim browsing, submission, and discovery votes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ModeratorUser, get_current_user, get_settings_dep
from app.core.config import Settings
from app.db.session import get_db
from app.models.evidence import EvidenceStance
from app.models.user import User
from app.models.claim import ProcessingStatus
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.claims_repository import ClaimRepository
from app.repositories.platform_repository import PlatformRepository
from app.services.ingestion.claim_normalization import normalize_claim_text
from app.services.ingestion.pipeline_audit import IngestionPipelineAudit
from app.schemas.claims import (
    AIAnalysisResponse,
    ClaimDetailResponse,
    ClaimListItemResponse,
    CreateClaimRequest,
    EvidenceResponse,
    PendingClaimResponse,
    ResubmitPendingRequest,
    VoteRequest,
)
from app.schemas.common import CursorMeta, SuccessEnvelope
from app.services.ai.factory import get_ai_provider
from app.services.claim_analysis_service import add_structured_verdict_for_claim
from app.utils.cursor import ClaimCursor, decode_cursor, encode_cursor
from app.workers.celery_app import process_pending_claim

router = APIRouter(tags=["claims"])


@router.post("/pending-claims", response_model=SuccessEnvelope[PendingClaimResponse])
async def submit_claim(
    body: CreateClaimRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SuccessEnvelope[PendingClaimResponse]:
    """Queue a new claim for async enrichment."""
    repo = ClaimRepository(db)
    normalized = normalize_claim_text(body.raw_claim_text)
    pending = await repo.create_pending(
        raw_text=normalized,
        user_id=user.id,
        source_urls=body.source_urls,
    )
    pending.normalized_claim_text = normalized
    platform = PlatformRepository(db)
    for url in (body.source_urls or [])[:20]:
        await platform.create_ingestion_job(pending_claim_id=pending.id, source_url=str(url))
    await IngestionPipelineAudit(db).log_submitted(
        pending_id=pending.id,
        actor_id=user.id,
        source_url_count=len(body.source_urls or []),
    )
    process_pending_claim.delay(str(pending.id))
    return SuccessEnvelope(data=PendingClaimResponse.model_validate(pending))


@router.get("/pending-claims/{pending_id}", response_model=SuccessEnvelope[PendingClaimResponse])
async def get_pending(
    pending_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SuccessEnvelope[PendingClaimResponse]:
    """Return pending submission if owned by caller."""
    repo = ClaimRepository(db)
    pending = await repo.get_pending(pending_id)
    if pending is None or pending.submitted_by != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return SuccessEnvelope(data=PendingClaimResponse.model_validate(pending))


@router.patch("/pending-claims/{pending_id}", response_model=SuccessEnvelope[PendingClaimResponse])
async def resubmit_pending(
    pending_id: UUID,
    body: ResubmitPendingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SuccessEnvelope[PendingClaimResponse]:
    """Revise and re-queue a submission after moderator requested revision."""
    repo = ClaimRepository(db)
    pending = await repo.get_pending(pending_id)
    if pending is None or pending.submitted_by != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    if ProcessingStatus(str(pending.processing_status)) != ProcessingStatus.revision_requested:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="not_revision_requested")
    pending.raw_claim_text = normalize_claim_text(body.raw_claim_text)
    pending.normalized_claim_text = pending.raw_claim_text
    if body.source_urls is not None:
        pending.source_urls = body.source_urls
    pending.processing_status = ProcessingStatus.submitted
    pending.error_message = None
    process_pending_claim.delay(str(pending.id))
    return SuccessEnvelope(data=PendingClaimResponse.model_validate(pending))


@router.get("/claims", response_model=SuccessEnvelope[list[ClaimListItemResponse]])
async def list_claims(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
    discovery: Annotated[bool, Query()] = False,
) -> SuccessEnvelope[list[ClaimListItemResponse]]:
    """Cursor-paginated approved claims."""
    repo = ClaimRepository(db)
    cur = None if discovery else decode_cursor(cursor)
    rows = await repo.list_claims_cursor(limit=limit + 1, cursor=cur, order_discovery=discovery)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_c = None
    if has_more and rows:
        last = rows[-1]
        next_c = encode_cursor(ClaimCursor(created_at=last.created_at, claim_id=last.id))
    data = [ClaimListItemResponse.model_validate(r) for r in rows]
    return SuccessEnvelope(
        data=data,
        meta=CursorMeta(next_cursor=next_c, previous_cursor=None, has_more=has_more).model_dump(),
    )


@router.post(
    "/claims/{slug}/ai-analysis",
    response_model=SuccessEnvelope[AIAnalysisResponse],
)
async def run_claim_ai_analysis(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _moderator: ModeratorUser,
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[AIAnalysisResponse]:
    """Run a structured verdict against the claim's evidence and store ai_analysis (moderators)."""
    repo = ClaimRepository(db)
    claim = await repo.load_claim_detail_bundle_by_slug(slug)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    provider = get_ai_provider(budget_scope=f"claim:{claim.id}")
    ai_repo = AIAnalysisRepository(db)
    row = await add_structured_verdict_for_claim(
        claim=claim,
        provider=provider,
        ai_repo=ai_repo,
        settings=settings,
    )
    return SuccessEnvelope(data=AIAnalysisResponse.model_validate(row))


@router.get("/claims/{slug}", response_model=SuccessEnvelope[ClaimDetailResponse])
async def claim_detail(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessEnvelope[ClaimDetailResponse]:
    """Public claim detail page payload."""
    repo = ClaimRepository(db)
    ai_repo = AIAnalysisRepository(db)
    claim = await repo.load_claim_detail_bundle_by_slug(slug)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    sup, con, ctx = [], [], []

    for ev in claim.evidence_items:
        item = EvidenceResponse.model_validate(ev)
        if ev.stance == EvidenceStance.supports:
            sup.append(item)
        elif ev.stance == EvidenceStance.contradicts:
            con.append(item)
        else:
            ctx.append(item)

    analyses = await ai_repo.list_for_target("claim", claim.id)
    ai_out = [AIAnalysisResponse.model_validate(a) for a in analyses[:12]]

    related = []
    if claim.embedding is not None:
        sim = await repo.vector_similar_claims(claim.embedding, limit=6, exclude_id=claim.id)
        related = [c.public_slug for c, _ in sim]

    detail = ClaimDetailResponse(
        id=claim.id,
        public_slug=claim.public_slug,
        canonical_claim_text=claim.canonical_claim_text,
        status=str(claim.status),
        confidence_score=float(claim.confidence_score),
        controversy_score=float(claim.controversy_score),
        evidence_score=float(claim.evidence_score),
        freshness_score=float(claim.freshness_score),
        evidence_count=claim.evidence_count,
        discovery_score=claim.discovery_score,
        aliases=[a.alias_text for a in claim.aliases],
        evidence_supporting=sup,
        evidence_contradicting=con,
        evidence_contextual=ctx,
        ai_analyses=ai_out,
        related_slugs=related,
    )
    return SuccessEnvelope(data=detail)


@router.post("/claims/{claim_id}/votes", response_model=SuccessEnvelope[dict])
async def vote_claim(
    claim_id: UUID,
    body: VoteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SuccessEnvelope[dict]:
    """Cast or update a discovery vote."""
    repo = ClaimRepository(db)
    claim = await repo.get_claim_by_id(claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    await repo.set_vote(claim_id, user.id, body.value)
    return SuccessEnvelope(data={"ok": True})
