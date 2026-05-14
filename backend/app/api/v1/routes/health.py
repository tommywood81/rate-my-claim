"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import SuccessEnvelope

router = APIRouter(tags=["health"])


def get_redis_client(request: Request) -> Redis:
    """Return Redis client from app state."""
    return request.app.state.redis


@router.get("/health", response_model=SuccessEnvelope[dict])
async def health() -> SuccessEnvelope[dict]:
    """Process up."""
    return SuccessEnvelope(data={"status": "ok"})


@router.get("/ready", response_model=SuccessEnvelope[dict])
async def ready(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> SuccessEnvelope[dict]:
    """Database and Redis connectivity."""
    await db.execute(text("SELECT 1"))
    await redis_client.ping()
    return SuccessEnvelope(data={"status": "ready"})
