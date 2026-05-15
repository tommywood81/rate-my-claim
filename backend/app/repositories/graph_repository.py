"""Claim graph primitives: aliases, revisions, relationships."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models.claim import ClaimAlias, ClaimRelationship, ClaimRevision, RelationshipType
from app.repositories.base import RepositoryBase


class GraphRepository(RepositoryBase):
    """Edges and immutable revision snapshots for approved claims."""

    async def add_alias(self, *, claim_id: UUID, alias_text: str) -> ClaimAlias:
        """Link an alternate phrasing to a claim."""
        row = ClaimAlias(claim_id=claim_id, alias_text=alias_text)
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_aliases(self, claim_id: UUID) -> list[ClaimAlias]:
        """Return aliases for a claim."""
        stmt = select(ClaimAlias).where(ClaimAlias.claim_id == claim_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def add_revision(
        self,
        *,
        claim_id: UUID,
        previous_status: str | None,
        new_status: str | None,
        previous_confidence: float | None,
        new_confidence: float | None,
        explanation: str | None,
        created_by: UUID | None,
    ) -> ClaimRevision:
        """Append an immutable revision snapshot."""
        row = ClaimRevision(
            claim_id=claim_id,
            previous_status=previous_status,
            new_status=new_status,
            previous_confidence=previous_confidence,
            new_confidence=new_confidence,
            explanation=explanation,
            created_by=created_by,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_revisions(self, claim_id: UUID, *, limit: int = 100) -> list[ClaimRevision]:
        """Return revisions newest first."""
        stmt = (
            select(ClaimRevision)
            .where(ClaimRevision.claim_id == claim_id)
            .order_by(desc(ClaimRevision.created_at))
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add_relationship(
        self,
        *,
        source_claim_id: UUID,
        target_claim_id: UUID,
        relationship_type: RelationshipType,
        strength: float | None = None,
        explanation: str | None = None,
        supporting_evidence_ids: list | None = None,
    ) -> ClaimRelationship:
        """Create a directed claim-to-claim edge."""
        row = ClaimRelationship(
            source_claim_id=source_claim_id,
            target_claim_id=target_claim_id,
            relationship_type=relationship_type,
            strength=strength,
            explanation=explanation,
            supporting_evidence_ids=supporting_evidence_ids,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_relationships_for_claim(
        self, claim_id: UUID, *, limit: int = 200
    ) -> list[ClaimRelationship]:
        """Return edges where the claim is source or target."""
        stmt = (
            select(ClaimRelationship)
            .where(
                (ClaimRelationship.source_claim_id == claim_id)
                | (ClaimRelationship.target_claim_id == claim_id)
            )
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
