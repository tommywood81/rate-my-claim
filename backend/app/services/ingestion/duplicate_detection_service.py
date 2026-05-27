"""Semantic duplicate candidate detection for pending submissions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.claim import PendingClaim
from app.repositories.claims_repository import ClaimRepository


@dataclass(frozen=True)
class DuplicateMatch:
    """Nearest library record that should block a new submission."""

    public_slug: str
    title: str
    similarity: float
    match_kind: str  # "claim" | "pending"
    match_method: str  # "exact" | "semantic"
    claim_id: UUID | None = None
    pending_id: UUID | None = None


class DuplicateDetectionService:
    """Find near-duplicate approved claims and pending submissions via pgvector."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """Attach DB session and optional settings."""
        self._session = session
        self._settings = settings or get_settings()
        self._claims = ClaimRepository(session)

    def _similarity(self, distance: float) -> float:
        return 1.0 - float(distance)

    async def find_exact_normalized_duplicate(self, normalized: str) -> DuplicateMatch | None:
        """Hash-first exact match on normalized submission text (no embedding API call)."""
        claim = await self._claims.find_claim_by_normalized_submission_text(normalized)
        if claim is not None:
            return DuplicateMatch(
                public_slug=claim.public_slug,
                title=(claim.canonical_claim_text or normalized)[:200],
                similarity=1.0,
                match_kind="claim",
                match_method="exact",
                claim_id=claim.id,
            )
        pending = await self._claims.find_pending_by_normalized_submission_text(normalized)
        if pending is not None:
            slug, title, claim_id = await self._resolve_pending_match(pending)
            if slug:
                return DuplicateMatch(
                    public_slug=slug,
                    title=title[:200],
                    similarity=1.0,
                    match_kind="pending",
                    match_method="exact",
                    claim_id=claim_id,
                    pending_id=pending.id,
                )
        return None

    async def find_semantic_blocking_duplicate(
        self,
        embedding: list[float],
        *,
        exclude_claim_id: UUID | None = None,
        exclude_pending_id: UUID | None = None,
    ) -> DuplicateMatch | None:
        """
        Return the best vector match at or above duplicate_vector_threshold, if any.
        """
        threshold = self._settings.duplicate_vector_threshold
        best: DuplicateMatch | None = None

        for claim, dist in await self._claims.vector_similar_claims(
            embedding, limit=12, exclude_id=exclude_claim_id
        ):
            sim = self._similarity(dist)
            if sim < threshold:
                continue
            if best is not None and sim <= best.similarity:
                continue
            best = DuplicateMatch(
                public_slug=claim.public_slug,
                title=(claim.canonical_claim_text or "")[:200],
                similarity=sim,
                match_kind="claim",
                match_method="semantic",
                claim_id=claim.id,
            )

        for other, dist in await self._claims.vector_similar_pending(
            embedding, limit=8, exclude_id=exclude_pending_id
        ):
            sim = self._similarity(dist)
            if sim < threshold:
                continue
            if best is not None and sim <= best.similarity:
                continue
            slug, title, claim_id = await self._resolve_pending_match(other)
            if not slug:
                continue
            best = DuplicateMatch(
                public_slug=slug,
                title=title[:200],
                similarity=sim,
                match_kind="pending",
                match_method="semantic",
                claim_id=claim_id,
                pending_id=other.id,
            )

        return best

    async def find_blocking_duplicate(
        self,
        embedding: list[float],
        *,
        exclude_claim_id: UUID | None = None,
        exclude_pending_id: UUID | None = None,
    ) -> DuplicateMatch | None:
        """Semantic duplicate check (used in enrichment pipeline)."""
        return await self.find_semantic_blocking_duplicate(
            embedding,
            exclude_claim_id=exclude_claim_id,
            exclude_pending_id=exclude_pending_id,
        )

    async def _resolve_pending_match(
        self, pending: PendingClaim
    ) -> tuple[str | None, str, UUID | None]:
        """Map a similar pending row to a public slug (via its linked live claim)."""
        if pending.linked_claim_id:
            linked = await self._claims.get_claim_by_id(pending.linked_claim_id)
            if linked is not None:
                return (
                    linked.public_slug,
                    linked.canonical_claim_text or pending.raw_claim_text,
                    linked.id,
                )
        return None, pending.raw_claim_text or "", None

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
            if self._similarity(dist) >= threshold:
                dup_ids.append(str(claim.id))
        for other, dist in await self._claims.vector_similar_pending(
            embedding, limit=pending_limit, exclude_id=pending_id
        ):
            if self._similarity(dist) >= threshold:
                dup_ids.append(f"pending:{other.id}")
        return dup_ids[:50]
