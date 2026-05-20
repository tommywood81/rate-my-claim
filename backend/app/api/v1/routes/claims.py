"""Public claim browsing, submission, and discovery votes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ModeratorUser, get_current_user, get_optional_current_user, get_settings_dep
from app.core.config import Settings
from app.core.csrf import generate_csrf_token, set_csrf_cookie
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
from app.services.claims.ai_analyses_display import dedupe_public_ai_analyses
from app.services.claims.claim_live_context import build_claim_live_context, merge_ai_analyses
from app.services.claims.live_claim_sync import ensure_live_claim_for_pending, get_pending_for_claim
from app.services.claims.pipeline_labels import visibility_label
from app.utils.cursor import ClaimCursor, decode_cursor, encode_cursor
from app.workers.celery_app import process_pending_claim

router = APIRouter(tags=["claims"])


def _pending_response(pending, *, slug: str | None = None) -> PendingClaimResponse:
    """Serialize pending row with optional live public slug."""
    data = PendingClaimResponse.model_validate(pending)
    if slug:
        return data.model_copy(update={"public_slug": slug})
    return data


@router.get("/csrf", response_model=SuccessEnvelope[dict])
async def issue_csrf_cookie(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[dict]:
    """Issue CSRF cookie for browser forms (guest submit and authenticated sessions)."""
    csrf = generate_csrf_token()
    set_csrf_cookie(response, csrf, settings)
    return SuccessEnvelope(data={}, meta={"csrf_token": csrf})


@router.post("/pending-claims", response_model=SuccessEnvelope[PendingClaimResponse])
async def submit_claim(
    body: CreateClaimRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_optional_current_user)],
) -> SuccessEnvelope[PendingClaimResponse]:
    """Queue a new claim for async enrichment (guests and signed-in users)."""
    repo = ClaimRepository(db)
    normalized = normalize_claim_text(body.raw_claim_text)
    pending = await repo.create_pending(
        raw_text=normalized,
        user_id=user.id if user else None,
        source_urls=body.source_urls,
    )
    pending.normalized_claim_text = normalized
    platform = PlatformRepository(db)
    for url in (body.source_urls or [])[:20]:
        await platform.create_ingestion_job(pending_claim_id=pending.id, source_url=str(url))
    await IngestionPipelineAudit(db).log_submitted(
        pending_id=pending.id,
        actor_id=user.id if user else None,
        source_url_count=len(body.source_urls or []),
        anonymous=user is None,
    )
    live_claim = await ensure_live_claim_for_pending(db, pending)
    await db.commit()
    process_pending_claim.delay(str(pending.id))
    meta: dict[str, str | bool] = {"anonymous": user is None, "public_slug": live_claim.public_slug}
    if user:
        meta["submitted_by"] = str(user.id)
        meta["message"] = (
            "Your claim is live. Research runs in the background; moderators may refine it at any time."
        )
    else:
        meta["message"] = (
            "Your claim is live. Sign in to link submissions to your account and revise after feedback."
        )
    return SuccessEnvelope(
        data=_pending_response(pending, slug=live_claim.public_slug),
        meta=meta,
    )


@router.get("/pending-claims/{pending_id}", response_model=SuccessEnvelope[PendingClaimResponse])
async def get_pending(
    pending_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SuccessEnvelope[PendingClaimResponse]:
    """Return pending submission if owned by caller."""
    repo = ClaimRepository(db)
    pending = await repo.get_pending(pending_id)
    if pending is None or pending.submitted_by is None or pending.submitted_by != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    slug = None
    if pending.linked_claim_id:
        linked = await repo.get_claim_by_id(pending.linked_claim_id)
        if linked:
            slug = linked.public_slug
    return SuccessEnvelope(data=_pending_response(pending, slug=slug))


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
    if pending is None or pending.submitted_by is None or pending.submitted_by != user.id:
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
    slug = None
    if pending.linked_claim_id:
        linked = await repo.get_claim_by_id(pending.linked_claim_id)
        if linked:
            slug = linked.public_slug
    return SuccessEnvelope(data=_pending_response(pending, slug=slug))


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
    pending_map = await repo.pending_by_linked_claim_ids([r.id for r in rows])
    data: list[ClaimListItemResponse] = []
    for row in rows:
        item = ClaimListItemResponse.model_validate(row)
        pending = pending_map.get(row.id)
        proc = str(pending.processing_status) if pending else None
        reviewed = row.last_reviewed_at is not None or (
            pending is not None and str(pending.processing_status) == "completed"
        )
        vis = visibility_label(
            processing_status=proc,
            claim_status=str(row.status),
            moderation_reviewed=reviewed,
        )
        data.append(item.model_copy(update={"processing_status": proc, "visibility_label": vis}))
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
    settings: Annotated[Settings, Depends(get_settings_dep)],
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
    seen_types: set[str] = set()
    deduped: list = []
    for row in analyses:
        if row.analysis_type in seen_types:
            continue
        seen_types.add(row.analysis_type)
        deduped.append(row)
        if len(deduped) >= 12:
            break
    ai_out = [AIAnalysisResponse.model_validate(a) for a in deduped]

    pending = await get_pending_for_claim(db, claim.id)
    live = await build_claim_live_context(db, claim=claim, pending=pending)
    ai_out = dedupe_public_ai_analyses(merge_ai_analyses(ai_out, live.pending_ai_analyses))

    related: list[str] = []
    if claim.embedding is not None:
        sim = await repo.vector_similar_claims(claim.embedding, limit=12, exclude_id=claim.id)
        floor = settings.enrichment_retrieval_min_similarity
        related = [c.public_slug for c, d in sim if (1.0 - float(d)) >= floor][:6]

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
        processing_status=live.processing_status,
        pipeline_stage_key=live.pipeline_stage_key,
        pipeline_stage_label=live.pipeline_stage_label,
        live_ai_summary=live.live_ai_summary,
        visibility_label=live.visibility_label,
        moderation_reviewed=live.moderation_reviewed,
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
