"""Evidence rows for approved claims."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.models.evidence import Evidence
from app.repositories.base import RepositoryBase


class EvidenceRepository(RepositoryBase):
    """Evidence persistence scoped to approved claims."""

    async def list_for_claim(self, claim_id: UUID) -> list[Evidence]:
        """Return all evidence rows for a claim."""
        stmt = select(Evidence).where(Evidence.claim_id == claim_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_id(self, evidence_id: UUID) -> Evidence | None:
        """Load a single evidence row."""
        stmt = select(Evidence).where(Evidence.id == evidence_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()
