"""Append auth events to audit_logs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repository import AuditRepository
from app.services.auth.request_context import AuthRequestContext


class SessionAudit:
    """Thin wrapper for security-relevant audit actions."""

    def __init__(self, session: AsyncSession) -> None:
        """Attach DB session."""
        self._audit = AuditRepository(session)

    async def log(
        self,
        *,
        action: str,
        ctx: AuthRequestContext,
        actor_id: UUID | None = None,
        resource_type: str | None = "user",
        resource_id: UUID | None = None,
        details: dict | None = None,
    ) -> None:
        """Write an audit_logs row."""
        await self._audit.append_audit_log(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            details=details,
            correlation_id=ctx.correlation_id,
        )
