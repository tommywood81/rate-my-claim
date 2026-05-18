"""Curated publication feed registry."""

from __future__ import annotations

from sqlalchemy import select

from app.models.evidence_feed import EvidenceSourceFeed
from app.repositories.base import RepositoryBase


class EvidenceFeedRepository(RepositoryBase):
    """RSS/API feed configuration."""

    async def list_enabled(self) -> list[EvidenceSourceFeed]:
        """Return feeds eligible for polling."""
        stmt = select(EvidenceSourceFeed).where(EvidenceSourceFeed.enabled.is_(True))
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_url(self, feed_url: str) -> EvidenceSourceFeed | None:
        """Lookup feed by URL."""
        stmt = select(EvidenceSourceFeed).where(EvidenceSourceFeed.feed_url == feed_url)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert_feed(
        self,
        *,
        name: str,
        feed_url: str,
        feed_type: str = "rss",
        publisher_name: str | None = None,
        credibility_score: float = 0.5,
    ) -> EvidenceSourceFeed:
        """Create feed if missing."""
        existing = await self.get_by_url(feed_url)
        if existing:
            return existing
        row = EvidenceSourceFeed(
            name=name,
            feed_url=feed_url,
            feed_type=feed_type,
            publisher_name=publisher_name,
            credibility_score=credibility_score,
            enabled=True,
        )
        self._session.add(row)
        await self._session.flush()
        return row
