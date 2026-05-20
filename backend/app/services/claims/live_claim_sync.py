"""Create and sync live public claims linked to pending enrichment (visibility layer)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ClaimStatus, PendingClaim, ProcessingStatus
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.claims_repository import ClaimRepository
from app.utils.slug import public_slug_for_claim

logger = logging.getLogger(__name__)


def _coerce_processing_status(value: ProcessingStatus | str) -> ProcessingStatus:
    """Normalize SQLAlchemy enum or string to ProcessingStatus."""
    if isinstance(value, ProcessingStatus):
        return value
    text = str(value)
    if text.startswith("ProcessingStatus."):
        text = text.split(".", 1)[1]
    return ProcessingStatus(text)


async def ensure_live_claim_for_pending(session: AsyncSession, pending: PendingClaim) -> Claim:
    """Create or return the public claim row for a pending submission."""
    if pending.linked_claim_id:
        claim = await session.get(Claim, pending.linked_claim_id)
        if claim is not None and claim.deleted_at is None:
            return claim

    claim_id = uuid4()
    canonical = pending.raw_claim_text.strip()
    slug = public_slug_for_claim(canonical, claim_id)
    normalized = pending.normalized_claim_text or canonical

    claim = Claim(
        id=claim_id,
        public_slug=slug,
        canonical_claim_text=canonical,
        normalized_claim_text=normalized,
        status=ClaimStatus.insufficient_evidence.value,
        confidence_score=0.0,
        controversy_score=0.0,
        evidence_score=0.0,
        freshness_score=0.5,
        evidence_count=0,
        created_by=pending.submitted_by,
    )
    session.add(claim)
    pending.linked_claim_id = claim.id
    await session.flush()
    logger.info(
        "live_claim_created",
        extra={"pending_id": str(pending.id), "claim_id": str(claim.id), "slug": slug},
    )
    return claim


def _scores_from_pending_analyses(analyses: list) -> tuple[float, float]:
    confidence = 0.0
    controversy = 0.0
    for row in analyses:
        if row.analysis_type == "confidence_analysis" and row.structured_payload:
            try:
                data = (
                    json.loads(row.structured_payload)
                    if isinstance(row.structured_payload, str)
                    else row.structured_payload
                )
                confidence = float(data.get("aggregate", 0.0) or 0.0)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        if row.analysis_type == "structured_verdict" and row.structured_payload:
            try:
                bundle = (
                    json.loads(row.structured_payload)
                    if isinstance(row.structured_payload, str)
                    else row.structured_payload
                )
                verdict = bundle.get("verdict", {}) or {}
                controversy = float(verdict.get("controversy_hint", 0.0) or 0.0)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    return confidence, controversy


async def sync_pending_to_linked_claim(session: AsyncSession, pending_id: UUID) -> None:
    """Push pending enrichment fields onto the linked public claim."""
    repo = ClaimRepository(session)
    pending = await repo.get_pending(pending_id)
    if pending is None or pending.linked_claim_id is None:
        return

    claim = await session.get(Claim, pending.linked_claim_id)
    if claim is None or claim.deleted_at is not None:
        return

    if pending.canonical_candidate_text:
        claim.canonical_claim_text = pending.canonical_candidate_text
    elif pending.raw_claim_text:
        claim.canonical_claim_text = pending.raw_claim_text

    if pending.normalized_claim_text:
        claim.normalized_claim_text = pending.normalized_claim_text

    if pending.embedding is not None:
        claim.embedding = pending.embedding
        claim.embedding_model = pending.embedding_model
        claim.embedding_version = pending.embedding_version
        claim.embedding_at = pending.embedding_at

    ai_repo = AIAnalysisRepository(session)
    analyses = await ai_repo.list_for_target("pending_claim", pending.id)
    confidence, controversy = _scores_from_pending_analyses(analyses)
    if confidence > 0 or controversy > 0:
        claim.confidence_score = confidence
        claim.controversy_score = controversy

    proc = _coerce_processing_status(pending.processing_status)
    if proc == ProcessingStatus.awaiting_moderation and analyses:
        if claim.status == ClaimStatus.insufficient_evidence.value:
            claim.status = ClaimStatus.weak_evidence.value

    claim.updated_at = datetime.now(tz=UTC)
    await session.flush()


async def get_pending_for_claim(session: AsyncSession, claim_id: UUID) -> PendingClaim | None:
    """Load the pending row linked to a public claim, if any."""
    from sqlalchemy import select

    stmt = select(PendingClaim).where(PendingClaim.linked_claim_id == claim_id)
    return (await session.execute(stmt)).scalar_one_or_none()
