"""Hybrid semantic + full-text candidate retrieval for claim search."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select

from app.core.metrics import observe_vector_query
from app.models.claim import Claim, ClaimRelationship
from app.repositories.base import RepositoryBase


class SearchRepository(RepositoryBase):
    """Fetch and filter claim search candidates from Postgres."""

    async def fetch_hybrid_candidates(
        self,
        *,
        query_text: str,
        query_embedding: list[float],
        candidate_limit: int,
        status: str | None = None,
        domain: str | None = None,
        min_confidence: float | None = None,
    ) -> list[tuple[UUID, float, float, int, float, float, int]]:
        """Return rows: id, vec_sim, fts, evidence_count, confidence, freshness, rel_count."""
        dist = Claim.embedding.cosine_distance(query_embedding)  # type: ignore[union-attr]
        vec_sim = (1.0 - dist).label("vec_sim")
        tsq = func.plainto_tsquery("english", query_text)
        fts = func.coalesce(func.ts_rank_cd(Claim.search_vector, tsq), 0.0).label("fts")
        rel_count_sq = (
            select(func.count())
            .select_from(ClaimRelationship)
            .where(
                or_(
                    ClaimRelationship.source_claim_id == Claim.id,
                    ClaimRelationship.target_claim_id == Claim.id,
                )
            )
            .correlate(Claim)
            .scalar_subquery()
        ).label("rel_count")

        stmt = (
            select(
                Claim.id,
                vec_sim,
                fts,
                Claim.evidence_count,
                Claim.confidence_score,
                Claim.freshness_score,
                rel_count_sq,
            )
            .where(Claim.deleted_at.is_(None), Claim.embedding.is_not(None))
            .order_by(dist)
            .limit(candidate_limit)
        )
        if status:
            stmt = stmt.where(Claim.status == status)
        if domain:
            stmt = stmt.where(Claim.domain == domain)
        if min_confidence is not None:
            stmt = stmt.where(Claim.confidence_score >= min_confidence)

        with observe_vector_query("hybrid_search"):
            rows = (await self._session.execute(stmt)).all()
        return [
            (
                row[0],
                float(row[1]),
                float(row[2]),
                int(row[3] or 0),
                float(row[4] or 0),
                float(row[5] or 0),
                int(row[6] or 0),
            )
            for row in rows
        ]

    async def load_claims_by_ids(self, claim_ids: list[UUID]) -> dict[UUID, Claim]:
        """Batch-load claims preserving no particular order."""
        if not claim_ids:
            return {}
        stmt = select(Claim).where(Claim.id.in_(claim_ids), Claim.deleted_at.is_(None))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {c.id: c for c in rows}
