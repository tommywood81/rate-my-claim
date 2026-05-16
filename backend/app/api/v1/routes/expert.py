"""Expert-only routes (Phase 3 RBAC)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ExpertUser
from app.db.session import get_db
from app.models.claim import Claim
from app.schemas.common import SuccessEnvelope

router = APIRouter(prefix="/expert", tags=["expert"])


@router.get("/summary", response_model=SuccessEnvelope[dict])
async def expert_summary(
    user: ExpertUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessEnvelope[dict]:
    """Expert dashboard stub proving RBAC (experts, moderators, admins)."""
    count = await db.scalar(select(func.count()).select_from(Claim).where(Claim.deleted_at.is_(None)))
    return SuccessEnvelope(
        data={
            "username": user.username,
            "role": user.role,
            "public_claims_count": int(count or 0),
        }
    )
