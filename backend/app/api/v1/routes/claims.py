"""Public claim browsing, submission, and discovery votes."""

from __future__ import annotations

from datetime import UTC, datetime
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
from app.services.ingestion.claim_normalization import normalize_claim_text
from app.services.ingestion.duplicate_detection_service import DuplicateDetectionService
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
from app.schemas.common import CursorMeta, ErrorDetail, ErrorEnvelope, SuccessEnvelope
from app.services.ai.factory import get_ai_provider
from app.services.claim_analysis_service import add_structured_verdict_for_claim
from app.services.claims.claim_ai_moderation import (
    collect_claim_ai_context,
    on_demand_analysis_available,
    on_demand_analysis_block_reason,
)
from app.services.claims.ai_analyses_display import dedupe_public_ai_analyses
from app.services.claims.assessment_provenance import filter_evidence_for_public_display
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
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[PendingClaimResponse]:
    """Queue a new claim for async enrichment (guests and signed-in users)."""
    repo = ClaimRepository(db)
    normalized = normalize_claim_text(body.raw_claim_text)
    dup_svc = DuplicateDetectionService(db, settings)

    exact = await dup_svc.find_exact_normalized_duplicate(normalized)
    if exact is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="duplicate_claim",
                    message=(
                        "This claim matches an existing record word-for-word. "
                        f"Open /claims/{exact.public_slug} instead of submitting again."
                    ),
                    details={
                        "similar_slug": exact.public_slug,
                        "similar_title": exact.title,
                        "similarity": 1.0,
                        "match_kind": exact.match_kind,
                        "match_method": exact.match_method,
                    },
                )
            ).model_dump(),
        )

    provider = get_ai_provider(budget_scope="submit:precheck")
    vec, emb_model = await provider.generate_embedding(normalized)
    dup = await dup_svc.find_semantic_blocking_duplicate(
        vec,
        threshold=settings.duplicate_submit_block_threshold,
    )
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="duplicate_claim",
                    message=(
                        "This claim is very similar to one already in the library. "
                        f"Open /claims/{dup.public_slug} instead of submitting again."
                    ),
                    details={
                        "similar_slug": dup.public_slug,
                        "similar_title": dup.title,
                        "similarity": round(dup.similarity, 4),
                        "match_kind": dup.match_kind,
                        "match_method": dup.match_method,
                    },
                )
            ).model_dump(),
        )

    pending = await repo.create_pending(
        raw_text=normalized,
        user_id=user.id if user else None,
        source_urls=[],
    )
    pending.normalized_claim_text = normalized
    pending.embedding = vec
    pending.embedding_model = emb_model
    pending.embedding_version = settings.embedding_version
    pending.embedding_at = datetime.now(tz=UTC)
    await IngestionPipelineAudit(db).log_submitted(
        pending_id=pending.id,
        actor_id=user.id if user else None,
        source_url_count=0,
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
        vis = visibility_label(
            processing_status=proc,
            claim_status=str(row.status),
            evidence_count=int(row.evidence_count or 0),
        )
        data.append(
            item.model_copy(
                update={
                    "processing_status": proc,
                    "visibility_label": vis,
                }
            )
        )
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
    ai_repo = AIAnalysisRepository(db)
    pending = await get_pending_for_claim(db, claim.id)
    combined, _ = await collect_claim_ai_context(
        ai_repo,
        claim_id=claim.id,
        pending_id=pending.id if pending is not None else None,
    )
    block = on_demand_analysis_block_reason(claim=claim, analyses=combined)
    if block:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=block)
    provider = get_ai_provider(budget_scope=f"claim:{claim.id}")
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

    for ev in filter_evidence_for_public_display(claim.evidence_items):
        item = EvidenceResponse.model_validate(ev)
        if ev.stance == EvidenceStance.supports:
            sup.append(item)
        elif ev.stance == EvidenceStance.contradicts:
            con.append(item)
        else:
            ctx.append(item)

    claim_analyses = await ai_repo.list_for_target("claim", claim.id)
    ai_out = [AIAnalysisResponse.model_validate(a) for a in claim_analyses[:24]]

    pending = await get_pending_for_claim(db, claim.id)
    live = await build_claim_live_context(db, claim=claim, pending=pending)
    ai_out = dedupe_public_ai_analyses(merge_ai_analyses(ai_out, live.pending_ai_analyses))

    from app.services.claims.claim_assessment import resolve_public_claim_scores

    pending_rows = (
        await ai_repo.list_for_target("pending_claim", pending.id) if pending is not None else []
    )
    combined_analyses, last_ai_run_at = await collect_claim_ai_context(
        ai_repo,
        claim_id=claim.id,
        pending_id=pending.id if pending is not None else None,
    )
    block_reason = on_demand_analysis_block_reason(claim=claim, analyses=combined_analyses)
    can_generate = on_demand_analysis_available(claim=claim, analyses=combined_analyses)

    confidence_score, controversy_score, evidence_score = resolve_public_claim_scores(
        claim, pending_analyses=pending_rows
    )

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
        confidence_score=confidence_score,
        controversy_score=controversy_score,
        evidence_score=evidence_score,
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
        assessment_complete=live.assessment_complete,
        staff_reviewed=live.staff_reviewed,
        moderation_reviewed=live.staff_reviewed,
        truth_label=live.truth_label,
        last_ai_run_at=last_ai_run_at,
        generate_ai_analysis_available=can_generate,
        generate_ai_analysis_block_reason=block_reason,
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
