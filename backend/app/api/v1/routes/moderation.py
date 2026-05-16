"""Moderation queue and actions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ModeratorUser
from app.db.session import get_db
from app.models.claim import PendingClaim, ProcessingStatus
from app.schemas.claims import ModerationActionRequest, PendingClaimResponse
from app.schemas.common import CursorMeta, SuccessEnvelope
from app.services.moderation.moderation_service import ModerationService
from app.utils.cursor import ClaimCursor, decode_cursor, encode_cursor

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/pending-claims", response_model=SuccessEnvelope[list[PendingClaimResponse]])
async def moderation_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    _mod: ModeratorUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> SuccessEnvelope[list[PendingClaimResponse]]:
    """List submissions in the enrichment/moderation pipeline (excludes completed/rejected)."""
    cur = decode_cursor(cursor)
    active = (
        ProcessingStatus.submitted,
        ProcessingStatus.embedding,
        ProcessingStatus.duplicate_check,
        ProcessingStatus.canonicalizing,
        ProcessingStatus.enriching,
        ProcessingStatus.awaiting_moderation,
        ProcessingStatus.failed,
    )
    stmt = (
        select(PendingClaim)
        .where(PendingClaim.processing_status.in_([s.value for s in active]))
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


@router.post("/actions", response_model=SuccessEnvelope[dict])
async def moderation_action(
    body: ModerationActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: ModeratorUser,
) -> SuccessEnvelope[dict]:
    """Execute a moderator action."""
    svc = ModerationService(db)
    if body.action_type == "approve_claim" and body.target_type == "pending_claim":
        claim = await svc.approve_pending(
            pending_id=body.target_id, actor_id=user.id, explanation=body.explanation
        )
        return SuccessEnvelope(data={"claim_id": str(claim.id), "slug": claim.public_slug})
    if body.action_type == "reject_claim" and body.target_type == "pending_claim":
        await svc.reject_pending(pending_id=body.target_id, actor_id=user.id, explanation=body.explanation)
        return SuccessEnvelope(data={"ok": True})
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_action")
