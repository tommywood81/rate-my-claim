"""Ingestion job queue operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models.ingestion import IngestionJob, IngestionJobStatus
from app.repositories.base import RepositoryBase


class IngestionJobRepository(RepositoryBase):
    """Fetch and update ingestion jobs."""

    async def list_for_pending(self, pending_id: UUID) -> list[IngestionJob]:
        """Queued or completed jobs for a pending claim."""
        stmt = (
            select(IngestionJob)
            .where(IngestionJob.pending_claim_id == pending_id)
            .order_by(IngestionJob.created_at)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_id(self, job_id: UUID) -> IngestionJob | None:
        """Load a single job."""
        return await self._session.get(IngestionJob, job_id)

    async def mark_running(self, job: IngestionJob) -> None:
        """Set job to running."""
        job.status = IngestionJobStatus.running
        await self._session.flush()

    async def mark_succeeded(
        self,
        job: IngestionJob,
        *,
        artifact_id: UUID,
        result_metadata: dict | None = None,
    ) -> None:
        """Complete job with linked artifact."""
        job.status = IngestionJobStatus.succeeded
        job.artifact_id = artifact_id
        job.result_metadata = result_metadata
        job.completed_at = datetime.now(tz=UTC)
        job.error_message = None
        await self._session.flush()

    async def mark_failed(self, job: IngestionJob, *, error: str) -> None:
        """Record failure."""
        job.status = IngestionJobStatus.failed
        job.error_message = error[:4000]
        job.completed_at = datetime.now(tz=UTC)
        await self._session.flush()
