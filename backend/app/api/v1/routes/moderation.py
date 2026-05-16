"""Moderation queue and actions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ModeratorUser
from app.db.session import get_db
from app.models.claim import ClaimStatus, PendingClaim, ProcessingStatus
from app.schemas.claims import ModerationActionRequest, PendingClaimResponse
from app.schemas.common import CursorMeta, ErrorDetail, ErrorEnvelope, SuccessEnvelope
from app.services.moderation.moderation_service import ModerationService
from app.utils.cursor import ClaimCursor, decode_cursor, encode_cursor
from app.workers.celery_app import process_pending_claim

router = APIRouter(prefix="/moderation", tags=["moderation"])

_ACTIVE_STATUSES = (
    ProcessingStatus.submitted,
    ProcessingStatus.embedding,
    ProcessingStatus.duplicate_check,
    ProcessingStatus.canonicalizing,
    ProcessingStatus.enriching,
    ProcessingStatus.awaiting_moderation,
    ProcessingStatus.revision_requested,
    ProcessingStatus.failed,
)


def _moderation_error(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ErrorEnvelope(
            error=ErrorDetail(code=str(exc), message="Moderation action failed.", details={})
        ).model_dump(),
    )


@router.get("/pending-claims", response_model=SuccessEnvelope[list[PendingClaimResponse]])
async def moderation_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    _mod: ModeratorUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> SuccessEnvelope[list[PendingClaimResponse]]:
    """List submissions in the enrichment/moderation pipeline (excludes completed/rejected)."""
    cur = decode_cursor(cursor)
    stmt = (
        select(PendingClaim)
        .where(PendingClaim.processing_status.in_([s.value for s in _ACTIVE_STATUSES]))
        .order_by(desc(PendingClaim.created_at), desc(PendingClaim.id))
    )
    if cur:
        stmt = stmt.where(
            (PendingClaim.created_at < cur.created_at)
            | ((PendingClaim.created_at == cur.created_at) & (PendingClaim.id < cur.claim_id))
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_c = None
    if has_more and rows:
        last = rows[-1]
        next_c = encode_cursor(ClaimCursor(created_at=last.created_at, claim_id=last.id))
    data = [PendingClaimResponse.model_validate(r) for r in rows]
    return SuccessEnvelope(
        data=data,
        meta=CursorMeta(next_cursor=next_c, previous_cursor=None, has_more=has_more).model_dump(),
    )


@router.post("/pending-claims/{pending_id}/reprocess", response_model=SuccessEnvelope[dict])
async def reprocess_pending_claim(
    pending_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ModeratorUser,
) -> SuccessEnvelope[dict]:
    """Re-run enrichment for a failed or revision-requested pending claim."""
    svc = ModerationService(db)
    try:
        await svc.reprocess_pending(pending_id=pending_id, actor_id=user.id)
    except ValueError as exc:
        raise _moderation_error(exc) from exc
    process_pending_claim.delay(str(pending_id))
    return SuccessEnvelope(data={"ok": True, "pending_id": str(pending_id)})


@router.post("/actions", response_model=SuccessEnvelope[dict])
async def moderation_action(
    body: ModerationActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ModeratorUser,
) -> SuccessEnvelope[dict]:
    """Execute a moderator action on pending or approved claims."""
    svc = ModerationService(db)
    try:
        if body.action_type == "approve_claim" and body.target_type == "pending_claim":
            claim = await svc.approve_pending(
                pending_id=body.target_id, actor_id=user.id, explanation=body.explanation
            )
            return SuccessEnvelope(
                data={"claim_id": str(claim.id), "slug": claim.public_slug}
            )
        if body.action_type == "reject_claim" and body.target_type == "pending_claim":
            await svc.reject_pending(
                pending_id=body.target_id, actor_id=user.id, explanation=body.explanation
            )
            return SuccessEnvelope(data={"ok": True})
        if body.action_type == "request_revision" and body.target_type == "pending_claim":
            await svc.request_revision_pending(
                pending_id=body.target_id, actor_id=user.id, explanation=body.explanation
            )
            return SuccessEnvelope(data={"ok": True})
        if body.action_type == "archive_claim" and body.target_type == "claim":
            claim = await svc.archive_claim(
                claim_id=body.target_id, actor_id=user.id, explanation=body.explanation
            )
            return SuccessEnvelope(
                data={"claim_id": str(claim.id), "status": str(claim.status)}
            )
        if body.action_type == "dispute_claim" and body.target_type == "claim":
            claim = await svc.dispute_claim(
                claim_id=body.target_id, actor_id=user.id, explanation=body.explanation
            )
            return SuccessEnvelope(
                data={"claim_id": str(claim.id), "status": str(claim.status)}
            )
        if body.action_type == "restore_claim" and body.target_type == "claim":
            target = ClaimStatus.weak_evidence
            if body.payload and body.payload.get("target_status"):
                try:
                    target = ClaimStatus(str(body.payload["target_status"]))
                except ValueError:
                    pass
            claim = await svc.restore_claim(
                claim_id=body.target_id,
                actor_id=user.id,
                explanation=body.explanation,
                target_status=target,
            )
            return SuccessEnvelope(data={"claim_id": str(claim.id), "status": str(claim.status)})
    except ValueError as exc:
        raise _moderation_error(exc) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_action")
