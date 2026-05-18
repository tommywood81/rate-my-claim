"""Poll RSS feeds and ingest linked articles."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import feedparser
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_feed import EvidenceSourceFeed
from app.repositories.evidence_feed_repository import EvidenceFeedRepository
from app.services.evidence.ingestion_service import EvidenceIngestionService

logger = logging.getLogger(__name__)


class RssFeedIngester:
    """Fetch RSS entries and ingest article URLs as evidence artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._feeds = EvidenceFeedRepository(session)
        self._ingestion = EvidenceIngestionService(session)

    async def poll_all_feeds(self, *, max_entries_per_feed: int = 5) -> int:
        """Poll enabled feeds; return count of successfully ingested URLs."""
        feeds = await self._feeds.list_enabled()
        total = 0
        for feed in feeds:
            total += await self.poll_feed(feed.id, max_entries=max_entries_per_feed)
        return total

    async def poll_feed(self, feed_id: UUID, *, max_entries: int = 5) -> int:
        """Poll one feed by id."""
        feed = await self._session.get(EvidenceSourceFeed, feed_id)
        if feed is None or not feed.enabled:
            return 0
        parsed = await asyncio.to_thread(feedparser.parse, feed.feed_url)
        ingested = 0
        for entry in (parsed.entries or [])[:max_entries]:
            link = str(getattr(entry, "link", "") or "").strip()
            if not link.startswith("http"):
                continue
            try:
                await self._ingestion.ingest_url(
                    link,
                    source_type="rss",
                    retrieval_source=f"rss_feed:{feed.name}",
                    budget_scope=f"rss:{feed.id}",
                )
                ingested += 1
            except Exception as exc:
                logger.info("rss_entry_ingest_skip", extra={"url": link, "error": str(exc)[:120]})
        feed.last_fetched_at = datetime.now(tz=UTC)
        await self._session.flush()
        return ingested
