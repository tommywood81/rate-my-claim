"""Persistence for audit logs and system events (immutable append-only)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select

from app.models.audit import AuditLog, SystemEvent
from app.repositories.base import RepositoryBase


class AuditRepository(RepositoryBase):
    """Append-only audit and domain event storage."""

    async def append_audit_log(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict | None = None,
        correlation_id: str | None = None,
    ) -> AuditLog:
        """Insert a single audit row."""
        row = AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            correlation_id=correlation_id,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def append_system_event(
        self,
        *,
        event_type: str,
        aggregate_type: str | None = None,
        aggregate_id: UUID | None = None,
        payload: dict | None = None,
    ) -> SystemEvent:
        """Record an internal domain event for future pipelines."""
        row = SystemEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_recent_audit_logs(self, *, limit: int = 50) -> list[AuditLog]:
        """Return newest audit entries (operations / security)."""
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_recent_system_events(self, *, limit: int = 50) -> list[SystemEvent]:
        """Return newest system events."""
        stmt = select(SystemEvent).order_by(desc(SystemEvent.created_at)).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())
