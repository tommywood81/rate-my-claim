"""Celery tasks for evidence ingestion jobs and RSS polling."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.services.evidence.ingestion_service import EvidenceIngestionService
from app.services.evidence.rss_ingester import RssFeedIngester

logger = logging.getLogger(__name__)


async def _process_job_async(job_id: UUID) -> None:
    async with AsyncSessionLocal() as session:
        jobs = IngestionJobRepository(session)
        job = await jobs.get_by_id(job_id)
        if job is None:
            return
        svc = EvidenceIngestionService(session)
        await svc.process_job(job)
        await session.commit()


async def _poll_rss_async() -> int:
    async with AsyncSessionLocal() as session:
        ingester = RssFeedIngester(session)
        count = await ingester.poll_all_feeds()
        await session.commit()
        return count


def run_process_ingestion_job(job_id: str) -> None:
    """Sync Celery entrypoint for a single ingestion job."""
    asyncio.run(_process_job_async(UUID(str(job_id))))


def run_poll_rss_feeds() -> int:
    """Sync Celery entrypoint to poll all enabled RSS feeds."""
    return asyncio.run(_poll_rss_async())
