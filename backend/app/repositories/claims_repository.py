"""Data access for claims, pending claims, and votes."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.core.metrics import observe_vector_query
from app.models.claim import Claim, ClaimRelationship, ClaimVote, PendingClaim, ProcessingStatus
from app.models.evidence import Evidence
from app.repositories.base import RepositoryBase
from app.utils.cursor import ClaimCursor


class ClaimRepository(RepositoryBase):
    """Async persistence helpers for claim aggregates."""

    async def get_claim_by_slug(self, slug: str) -> Claim | None:
        """Load approved claim by public slug."""
        stmt = select(Claim).where(Claim.public_slug == slug, Claim.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_claim_by_id(self, claim_id: UUID) -> Claim | None:
        """Load claim by primary key."""
        stmt = select(Claim).where(Claim.id == claim_id, Claim.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_claims_cursor(
        self,
        *,
        limit: int,
        cursor: ClaimCursor | None,
        order_discovery: bool = False,
    ) -> Sequence[Claim]:
        """Keyset-paginated claim list."""
        stmt: Select[tuple[Claim]] = select(Claim).where(Claim.deleted_at.is_(None))
        if order_discovery:
            stmt = stmt.order_by(Claim.discovery_score.desc(), Claim.updated_at.desc(), Claim.id.desc())
        else:
            stmt = stmt.order_by(Claim.created_at.desc(), Claim.id.desc())
        if cursor:
            stmt = stmt.where(
                (Claim.created_at < cursor.created_at)
                | ((Claim.created_at == cursor.created_at) & (Claim.id < cursor.claim_id))
            )
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_claims_with_embeddings(self, *, limit: int) -> Sequence[Claim]:
        """Claims that have vector embeddings, for atlas projection."""
        stmt = (
            select(Claim)
            .where(Claim.deleted_at.is_(None), Claim.embedding.is_not(None))
            .order_by(Claim.updated_at.desc(), Claim.id.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_claims_with_embeddings(self) -> int:
        """Total indexed claims with embeddings (may exceed atlas display cap)."""
        stmt = select(func.count()).select_from(Claim).where(
            Claim.deleted_at.is_(None),
            Claim.embedding.is_not(None),
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def vector_similar_claims(
        self, embedding: list[float], *, limit: int, exclude_id: UUID | None = None
    ) -> Sequence[tuple[Claim, float]]:
        """Return nearest claims by cosine distance (lower is closer)."""
        distance = Claim.embedding.cosine_distance(embedding)  # type: ignore[union-attr]
        stmt = (
            select(Claim, distance.label("dist"))
            .where(Claim.embedding.is_not(None), Claim.deleted_at.is_(None))
            .order_by(distance)
            .limit(limit)
        )
        if exclude_id:
            stmt = stmt.where(Claim.id != exclude_id)
        with observe_vector_query("similar_claims"):
            rows = (await self._session.execute(stmt)).all()
        return [(c, float(d)) for c, d in rows]

    async def vector_similar_pending(
        self, embedding: list[float], *, limit: int, exclude_id: UUID | None = None
    ) -> Sequence[tuple[PendingClaim, float]]:
        """Find similar pending submissions for duplicate review."""
        distance = PendingClaim.embedding.cosine_distance(embedding)  # type: ignore[union-attr]
        stmt = (
            select(PendingClaim, distance.label("dist"))
            .where(PendingClaim.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        if exclude_id:
            stmt = stmt.where(PendingClaim.id != exclude_id)
        with observe_vector_query("similar_pending"):
            rows = (await self._session.execute(stmt)).all()
        return [(p, float(d)) for p, d in rows]

    async def get_pending(self, pending_id: UUID) -> PendingClaim | None:
        """Load pending claim row."""
        stmt = select(PendingClaim).where(PendingClaim.id == pending_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def pending_by_linked_claim_ids(
        self, claim_ids: list[UUID]
    ) -> dict[UUID, PendingClaim]:
        """Map public claim ids to their linked pending pipeline row."""
        if not claim_ids:
            return {}
        stmt = select(PendingClaim).where(PendingClaim.linked_claim_id.in_(claim_ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {p.linked_claim_id: p for p in rows if p.linked_claim_id is not None}

    async def save_pending(self, pending: PendingClaim) -> PendingClaim:
        """Insert or update pending claim."""
        self._session.add(pending)
        await self._session.flush()
        return pending

    async def create_pending(
        self,
        *,
        raw_text: str,
        user_id: UUID | None,
        source_urls: list[str] | None,
    ) -> PendingClaim:
        """Create a new pending submission (guest when user_id is None)."""
        pending = PendingClaim(
            raw_claim_text=raw_text,
            submitted_by=user_id,
            source_urls=source_urls or [],
            processing_status=ProcessingStatus.submitted,
        )
        self._session.add(pending)
        await self._session.flush()
        return pending

    async def count_votes_for_user(self, claim_id: UUID, user_id: UUID) -> int:
        """Return existing vote value or 0 if none."""
        stmt = select(ClaimVote.value).where(
            ClaimVote.claim_id == claim_id, ClaimVote.user_id == user_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(row) if row is not None else 0

    async def set_vote(self, claim_id: UUID, user_id: UUID, value: int) -> None:
        """Upsert vote and adjust discovery_score on claim."""
        existing = await self._session.execute(
            select(ClaimVote).where(
                ClaimVote.claim_id == claim_id, ClaimVote.user_id == user_id
            )
        )
        vote = existing.scalar_one_or_none()
        prev = vote.value if vote else 0
        delta = value - prev
        if vote:
            if value == 0:
                await self._session.delete(vote)
            else:
                vote.value = value
        elif value != 0:
            self._session.add(ClaimVote(claim_id=claim_id, user_id=user_id, value=value))
        if delta != 0:
            await self._session.execute(
                update(Claim)
                .where(Claim.id == claim_id)
                .values(discovery_score=Claim.discovery_score + delta)
            )

    async def load_claim_detail_bundle(self, claim_id: UUID) -> Claim | None:
        """Claim with evidence and aliases for API assembly."""
        stmt = (
            select(Claim)
            .options(selectinload(Claim.evidence_items), selectinload(Claim.aliases))
            .where(Claim.id == claim_id, Claim.deleted_at.is_(None))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def load_claim_detail_bundle_by_slug(self, slug: str) -> Claim | None:
        """Load claim graph by public slug."""
        claim = await self.get_claim_by_slug(slug)
        if claim is None:
            return None
        return await self.load_claim_detail_bundle(claim.id)

    async def evidence_for_similar_claims(
        self,
        embedding: list[float],
        *,
        limit: int,
        min_similarity: float = 0.72,
        exclude_claim_id: UUID | None = None,
    ) -> Sequence[Evidence]:
        """Retrieve evidence from semantically similar claims above a similarity floor."""
        similar = await self.vector_similar_claims(
            embedding, limit=12, exclude_id=exclude_claim_id
        )
        claim_ids: list[UUID] = []
        for claim, dist in similar:
            if (1.0 - float(dist)) < min_similarity:
                continue
            claim_ids.append(claim.id)
            if len(claim_ids) >= 6:
                break
        if not claim_ids:
            return []
        stmt = select(Evidence).where(Evidence.claim_id.in_(claim_ids)).limit(limit)
        return (await self._session.execute(stmt)).scalars().all()


class HybridSearchRepository(RepositoryBase):
    """Deprecated: use ``ClaimSearchService`` + ``SearchRepository`` (Phase 7)."""

    async def hybrid_search(
        self,
        *,
        query_text: str,
        query_embedding: list[float],
        limit: int,
        settings,
    ) -> list[tuple[Claim, float]]:
        """Backward-compatible shim delegating to Phase 7 search stack."""
        from app.repositories.search_repository import SearchRepository
        from app.services.search.hybrid_ranking import build_scored_claims

        repo = SearchRepository(self._session)
        raw = await repo.fetch_hybrid_candidates(
            query_text=query_text,
            query_embedding=query_embedding,
            candidate_limit=max(limit * 4, 20),
        )
        scored = build_scored_claims(raw, settings)
        claim_map = await repo.load_claims_by_ids([UUID(s.claim_id) for s in scored])
        out: list[tuple[Claim, float]] = []
        for s in scored[:limit]:
            claim = claim_map.get(UUID(s.claim_id))
            if claim:
                out.append((claim, s.final_score))
        return out
