"""User profile routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.users_repository import UserRepository
from app.schemas.auth import UserPublicResponse
from app.schemas.common import SuccessEnvelope

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=SuccessEnvelope[UserPublicResponse])
async def get_user_profile(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessEnvelope[UserPublicResponse]:
    """Public profile lookup."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return SuccessEnvelope(data=UserPublicResponse.model_validate(user))
