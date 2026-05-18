"""Cross-cutting domain tables: moderation, reputation, publishers, ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select

from app.models.ingestion import IngestionJob, IngestionJobStatus
from app.models.moderation import ModerationAction
from app.models.publisher import PublisherProfile
from app.models.reputation import ReputationEvent
from app.repositories.base import RepositoryBase


class PlatformRepository(RepositoryBase):
    """Moderation ledger, reputation, publishers, and ingestion jobs."""

    async def get_publisher_by_name(self, name: str) -> PublisherProfile | None:
        """Load publisher profile by unique name."""
        stmt = select(PublisherProfile).where(PublisherProfile.publisher_name == name)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert_publisher(
        self,
        *,
        publisher_name: str,
        credibility_score: float = 0.5,
        bias_notes: str | None = None,
        expertise_domains: list | None = None,
        review_status: str = "approved",
    ) -> PublisherProfile:
        """Insert or return existing publisher by name."""
        existing = await self.get_publisher_by_name(publisher_name)
        if existing:
            return existing
        row = PublisherProfile(
            publisher_name=publisher_name,
            credibility_score=credibility_score,
            bias_notes=bias_notes,
            expertise_domains=expertise_domains,
            review_status=review_status,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def create_ingestion_job(
        self,
        *,
        source_url: str,
        pending_claim_id: UUID | None = None,
        status: IngestionJobStatus = IngestionJobStatus.queued,
    ) -> IngestionJob:
        """Queue a URL fetch job."""
        row = IngestionJob(
            pending_claim_id=pending_claim_id,
            source_url=source_url,
            status=status,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def append_reputation_event(
        self,
        *,
        user_id: UUID,
        delta: float,
        reason: str,
        explanation: str | None = None,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        payload: dict | None = None,
    ) -> ReputationEvent:
        """Record an explainable reputation delta."""
        row = ReputationEvent(
            user_id=user_id,
            delta=delta,
            reason=reason,
            explanation=explanation,
            reference_type=reference_type,
            reference_id=reference_id,
            payload=payload,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_moderation_actions(
        self, *, target_type: str | None = None, limit: int = 100
    ) -> list[ModerationAction]:
        """Return recent moderation actions, optionally filtered by target type."""
        stmt = select(ModerationAction).order_by(desc(ModerationAction.created_at)).limit(limit)
        if target_type:
            stmt = stmt.where(ModerationAction.target_type == target_type)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_moderation_for_target(
        self, target_id: UUID, *, target_type: str | None = None, limit: int = 100
    ) -> list[ModerationAction]:
        """Return moderation actions for a specific claim or pending target."""
        stmt = (
            select(ModerationAction)
            .where(ModerationAction.target_id == target_id)
            .order_by(desc(ModerationAction.created_at))
            .limit(limit)
        )
        if target_type:
            stmt = stmt.where(ModerationAction.target_type == target_type)
        return list((await self._session.execute(stmt)).scalars().all())
