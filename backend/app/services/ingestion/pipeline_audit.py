"""Audit and domain events for the claim ingestion pipeline."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repository import AuditRepository


class IngestionPipelineAudit:
    """Append-only audit trail for enrichment stages."""

    def __init__(self, session: AsyncSession) -> None:
        """Attach DB session."""
        self._audit = AuditRepository(session)

    async def log_stage(
        self,
        *,
        pending_id: UUID,
        stage: str,
        details: dict | None = None,
        actor_id: UUID | None = None,
    ) -> None:
        """Record a pipeline stage transition."""
        await self._audit.append_audit_log(
            actor_id=actor_id,
            action=f"ingestion_{stage}",
            resource_type="pending_claim",
            resource_id=pending_id,
            details=details,
        )
        await self._audit.append_system_event(
            event_type=f"claim_pipeline_{stage}",
            aggregate_type="pending_claim",
            aggregate_id=pending_id,
            payload=details,
        )

    async def log_submitted(
        self,
        *,
        pending_id: UUID,
        actor_id: UUID | None,
        source_url_count: int,
        anonymous: bool = False,
    ) -> None:
        """User submitted a new pending claim."""
        await self.log_stage(
            pending_id=pending_id,
            stage="submitted",
            actor_id=actor_id,
            details={"source_url_count": source_url_count, "anonymous": anonymous},
        )
