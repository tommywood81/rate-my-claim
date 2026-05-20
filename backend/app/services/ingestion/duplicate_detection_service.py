"""Semantic duplicate candidate detection for pending submissions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.repositories.claims_repository import ClaimRepository


class DuplicateDetectionService:
    """Find near-duplicate approved claims and pending submissions via pgvector."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """Attach DB session and optional settings."""
        self._session = session
        self._settings = settings or get_settings()
        self._claims = ClaimRepository(session)

    async def find_duplicate_candidate_ids(
        self,
        embedding: list[float],
        *,
        pending_id: UUID,
        exclude_claim_id: UUID | None = None,
        claim_limit: int = 12,
        pending_limit: int = 8,
    ) -> list[str]:
        """Return claim UUIDs and pending:UUID strings above similarity threshold."""
        threshold = self._settings.duplicate_vector_threshold
        dup_ids: list[str] = []
        for claim, dist in await self._claims.vector_similar_claims(
            embedding, limit=claim_limit, exclude_id=exclude_claim_id
        ):
            if exclude_claim_id and claim.id == exclude_claim_id:
                continue
            if 1.0 - float(dist) >= threshold:
                dup_ids.append(str(claim.id))
        for other, dist in await self._claims.vector_similar_pending(
            embedding, limit=pending_limit, exclude_id=pending_id
        ):
            if 1.0 - float(dist) >= threshold:
                dup_ids.append(f"pending:{other.id}")
        return dup_ids[:50]
