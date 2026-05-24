"""Moderator workflows with immutable audit records."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ClaimRevision, ClaimStatus, ProcessingStatus
from app.models.moderation import ModerationAction, ModerationActionType
from app.core.metrics import record_moderation
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.claims_repository import ClaimRepository
from app.services.moderation.state_machine import (
    assert_claim_status_transition,
    assert_pending_transition,
)
from app.services.claims.live_claim_sync import sync_pending_to_linked_claim

logger = logging.getLogger(__name__)


class ModerationService:
    """Apply moderation actions with audit logging."""

    def __init__(self, session: AsyncSession) -> None:
        """Attach async session."""
        self._session = session
        self._claims = ClaimRepository(session)
        self._ai = AIAnalysisRepository(session)

    async def _log_action(
        self,
        *,
        actor_id: UUID,
        action_type: ModerationActionType,
        target_type: str,
        target_id: UUID,
        explanation: str | None,
        payload: dict | None,
    ) -> None:
        """Insert moderation action row."""
        self._session.add(
            ModerationAction(
                actor_id=actor_id,
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                explanation=explanation,
                payload=payload,
                created_at=datetime.now(tz=UTC),
            )
        )
        action_name = (
            action_type.value if hasattr(action_type, "value") else str(action_type)
        )
        record_moderation(action_name)

    async def approve_pending(
        self,
        *,
        pending_id: UUID,
        actor_id: UUID,
        explanation: str | None,
        force_duplicate: bool = False,
    ) -> Claim:
        """Re-publish assessment to the live claim (maintenance; not a human approval gate)."""
        from app.services.claims.assessment_finalize import finalize_pending_assessment

        pending = await self._claims.get_pending(pending_id)
        if pending is None:
            raise ValueError("pending_not_found")
        current = ProcessingStatus(str(pending.processing_status))
        if current not in {
            ProcessingStatus.awaiting_moderation,
            ProcessingStatus.completed,
        }:
            assert_pending_transition(current, ProcessingStatus.completed)

        if not force_duplicate:
            for raw_id in pending.duplicate_candidate_ids or []:
                if not isinstance(raw_id, str) or raw_id.startswith("pending:"):
                    continue
                try:
                    existing_id = UUID(raw_id)
                except ValueError:
                    continue
                existing = await self._claims.get_claim_by_id(existing_id)
                if existing is not None:
                    raise ValueError(f"duplicate_of_claim:{existing.public_slug}")

        claim = await finalize_pending_assessment(
            self._session,
            pending_id,
            actor_id=actor_id,
            created_by_job="maintenance_resync",
            explanation=explanation or "Assessment re-synced by staff.",
        )
        if claim is None:
            raise ValueError("linked_claim_not_found")

        await self._log_action(
            actor_id=actor_id,
            action_type=ModerationActionType.approve_claim,
            target_type="pending_claim",
            target_id=pending_id,
            explanation=explanation,
            payload={"claim_id": str(claim.id), "maintenance_resync": True},
        )
        return claim

    async def reject_pending(
        self, *, pending_id: UUID, actor_id: UUID, explanation: str | None
    ) -> None:
        """Reject a pending submission."""
        pending = await self._claims.get_pending(pending_id)
        if pending is None:
            raise ValueError("pending_not_found")
        current = ProcessingStatus(str(pending.processing_status))
        assert_pending_transition(current, ProcessingStatus.rejected)
        pending.processing_status = ProcessingStatus.rejected
        if pending.linked_claim_id:
            linked = await self._claims.get_claim_by_id(pending.linked_claim_id)
            if linked is not None:
                linked.status = ClaimStatus.archived.value
                linked.last_reviewed_at = datetime.now(tz=UTC)
        await self._log_action(
            actor_id=actor_id,
            action_type=ModerationActionType.reject_claim,
            target_type="pending_claim",
            target_id=pending_id,
            explanation=explanation,
            payload=None,
        )

    async def request_revision_pending(
        self, *, pending_id: UUID, actor_id: UUID, explanation: str | None
    ) -> None:
        """Send pending claim back to submitter for revision."""
        pending = await self._claims.get_pending(pending_id)
        if pending is None:
            raise ValueError("pending_not_found")
        current = ProcessingStatus(str(pending.processing_status))
        assert_pending_transition(current, ProcessingStatus.revision_requested)
        pending.processing_status = ProcessingStatus.revision_requested
        await self._log_action(
            actor_id=actor_id,
            action_type=ModerationActionType.request_revision,
            target_type="pending_claim",
            target_id=pending_id,
            explanation=explanation,
            payload=None,
        )

    async def reprocess_pending(self, *, pending_id: UUID, actor_id: UUID | None) -> None:
        """Reset pipeline to submitted for Celery re-run (failed or revision only)."""
        pending = await self._claims.get_pending(pending_id)
        if pending is None:
            raise ValueError("pending_not_found")
        current = ProcessingStatus(str(pending.processing_status))
        if current not in {ProcessingStatus.failed, ProcessingStatus.revision_requested}:
            raise ValueError("reprocess_not_allowed")
        assert_pending_transition(current, ProcessingStatus.submitted)
        pending.processing_status = ProcessingStatus.submitted
        pending.error_message = None
        pending.ai_summary = None
        await sync_pending_to_linked_claim(self._session, pending_id)
        await self._log_action(
            actor_id=actor_id,
            action_type=ModerationActionType.update_scores,
            target_type="pending_claim",
            target_id=pending_id,
            explanation="Re-queued for enrichment",
            payload={"reprocess": True},
        )

    async def _apply_claim_status(
        self,
        *,
        claim: Claim,
        new_status: ClaimStatus,
        actor_id: UUID,
        explanation: str | None,
        action_type: ModerationActionType,
    ) -> Claim:
        """Transition claim status with revision history and audit row."""
        prev = ClaimStatus(str(claim.status))
        assert_claim_status_transition(prev, new_status)
        self._session.add(
            ClaimRevision(
                claim_id=claim.id,
                previous_status=str(prev.value),
                new_status=str(new_status.value),
                previous_confidence=claim.confidence_score,
                new_confidence=claim.confidence_score,
                explanation=explanation,
                created_by=actor_id,
                created_at=datetime.now(tz=UTC),
            )
        )
        claim.status = new_status.value
        claim.last_reviewed_at = datetime.now(tz=UTC)
        await self._log_action(
            actor_id=actor_id,
            action_type=action_type,
            target_type="claim",
            target_id=claim.id,
            explanation=explanation,
            payload={"previous_status": str(prev.value), "new_status": str(new_status.value)},
        )
        await self._session.flush()
        return claim

    async def dispute_claim(
        self, *, claim_id: UUID, actor_id: UUID, explanation: str | None
    ) -> Claim:
        """Mark an approved claim as disputed."""
        claim = await self._claims.get_claim_by_id(claim_id)
        if claim is None:
            raise ValueError("claim_not_found")
        return await self._apply_claim_status(
            claim=claim,
            new_status=ClaimStatus.disputed,
            actor_id=actor_id,
            explanation=explanation,
            action_type=ModerationActionType.update_scores,
        )

    async def archive_claim(
        self, *, claim_id: UUID, actor_id: UUID, explanation: str | None
    ) -> Claim:
        """Archive an approved claim."""
        claim = await self._claims.get_claim_by_id(claim_id)
        if claim is None:
            raise ValueError("claim_not_found")
        return await self._apply_claim_status(
            claim=claim,
            new_status=ClaimStatus.archived,
            actor_id=actor_id,
            explanation=explanation,
            action_type=ModerationActionType.archive_claim,
        )

    async def restore_claim(
        self,
        *,
        claim_id: UUID,
        actor_id: UUID,
        explanation: str | None,
        target_status: ClaimStatus = ClaimStatus.weak_evidence,
    ) -> Claim:
        """Restore disputed or archived claim to an active status."""
        claim = await self._claims.get_claim_by_id(claim_id)
        if claim is None:
            raise ValueError("claim_not_found")
        return await self._apply_claim_status(
            claim=claim,
            new_status=target_status,
            actor_id=actor_id,
            explanation=explanation,
            action_type=ModerationActionType.update_scores,
        )
