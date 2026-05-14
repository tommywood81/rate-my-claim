"""Moderator workflows with immutable audit records."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ClaimRevision, ClaimStatus, PendingClaim, ProcessingStatus
from app.models.evidence import Evidence, EvidenceSourceType, EvidenceStance
from app.models.moderation import ModerationAction, ModerationActionType
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.claims_repository import ClaimRepository
from app.services.ai.factory import get_ai_provider
from app.utils.slug import public_slug_for_claim

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

    async def approve_pending(self, *, pending_id: UUID, actor_id: UUID, explanation: str | None) -> Claim:
        """Promote pending submission to an approved claim with evidence."""
        pending = await self._claims.get_pending(pending_id)
        if pending is None:
            raise ValueError("pending_not_found")
        if pending.processing_status != ProcessingStatus.awaiting_moderation:
            raise ValueError("invalid_pending_state")

        canonical = pending.canonical_candidate_text or pending.raw_claim_text
        new_id = uuid4()
        slug = public_slug_for_claim(canonical, new_id)

        confidence = 0.0
        controversy = 0.0
        analyses = await self._ai.list_for_target("pending_claim", pending_id)
        for row in analyses:
            if row.analysis_type == "confidence_analysis" and row.structured_payload:
                try:
                    data = json.loads(row.structured_payload)
                    confidence = float(data.get("aggregate", 0.0) or 0.0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
            if row.analysis_type == "structured_verdict" and row.structured_payload:
                try:
                    bundle = json.loads(row.structured_payload)
                    controversy = float(bundle.get("verdict", {}).get("controversy_hint", 0.0) or 0.0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

        claim = Claim(
            id=new_id,
            public_slug=slug,
            canonical_claim_text=canonical,
            normalized_claim_text=pending.normalized_claim_text or canonical,
            embedding=pending.embedding,
            embedding_model=pending.embedding_model,
            embedding_version=pending.embedding_version,
            embedding_at=pending.embedding_at,
            domain=None,
            status=ClaimStatus.insufficient_evidence,
            confidence_score=confidence,
            controversy_score=controversy,
            evidence_score=0.0,
            freshness_score=0.5,
            evidence_count=0,
            created_by=pending.submitted_by,
        )
        self._session.add(claim)

        verdict_bundle: dict | None = None
        for row in analyses:
            if row.analysis_type == "structured_verdict" and row.structured_payload:
                try:
                    verdict_bundle = json.loads(row.structured_payload)
                    break
                except json.JSONDecodeError:
                    continue

        evidence_added = 0
        provider = get_ai_provider()
        if verdict_bundle:
            line_map_raw = verdict_bundle.get("line_map") or {}
            line_map: dict[int, dict] = {}
            for k, v in line_map_raw.items():
                try:
                    line_map[int(k)] = v  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
            verdict = verdict_bundle.get("verdict") or {}
            for cit in verdict.get("citations", []) or []:
                try:
                    line_no = int(cit.get("context_line", -1))
                except (TypeError, ValueError):
                    continue
                block = line_map.get(line_no)
                if not block or block.get("kind") != "url":
                    continue
                stance_str = str(cit.get("stance", "contextualizes")).lower()
                stance = (
                    EvidenceStance.supports
                    if stance_str == "supports"
                    else EvidenceStance.contradicts
                    if stance_str == "contradicts"
                    else EvidenceStance.contextualizes
                )
                ev = Evidence(
                    claim_id=claim.id,
                    source_type=EvidenceSourceType.manual_url,
                    title=str(block.get("title") or block.get("url")),
                    url=str(block.get("url")),
                    publisher=str(block.get("publisher") or "") or None,
                    summary=str(cit.get("note", ""))[:4000],
                    cleaned_content=str(block.get("text", ""))[:8000],
                    stance=stance,
                    credibility_score=0.5,
                    retrieval_timestamp=datetime.now(tz=UTC),
                    retrieval_source="moderation_approve",
                    created_by=actor_id,
                )
                self._session.add(ev)
                text_for_emb = f"{ev.title}\n{ev.summary or ''}\n{ev.cleaned_content or ''}"[:8000]
                vec, emb_model = await provider.generate_embedding(text_for_emb)
                ev.embedding = vec
                ev.embedding_model = emb_model
                ev.embedding_version = pending.embedding_version
                evidence_added += 1

        await self._session.flush()
        claim.evidence_count = evidence_added
        claim.evidence_score = min(1.0, 0.2 * evidence_added)
        if evidence_added > 0:
            claim.status = ClaimStatus.weak_evidence

        pending.processing_status = ProcessingStatus.completed
        self._session.add(
            ClaimRevision(
                claim_id=claim.id,
                previous_status=None,
                new_status=str(claim.status),
                previous_confidence=None,
                new_confidence=claim.confidence_score,
                explanation=explanation,
                created_by=actor_id,
                created_at=datetime.now(tz=UTC),
            )
        )
        await self._log_action(
            actor_id=actor_id,
            action_type=ModerationActionType.approve_claim,
            target_type="pending_claim",
            target_id=pending_id,
            explanation=explanation,
            payload={"claim_id": str(claim.id)},
        )
        await self._session.flush()
        logger.info("claim_approved", extra={"claim_id": str(claim.id), "pending_id": str(pending_id)})

        for row in analyses:
            if row.analysis_type in {"structured_verdict", "confidence_analysis"}:
                payload = None
                if row.structured_payload:
                    try:
                        payload = json.loads(row.structured_payload)
                    except json.JSONDecodeError:
                        payload = None
                await self._ai.add_analysis(
                    target_type="claim",
                    target_id=claim.id,
                    model_name=row.model_name,
                    provider=row.provider,
                    analysis_type=row.analysis_type,
                    generated_text=row.generated_text,
                    structured_payload=payload,
                    confidence=row.confidence,
                    created_by_job="approval_import",
                )

        return claim

    async def reject_pending(
        self, *, pending_id: UUID, actor_id: UUID, explanation: str | None
    ) -> None:
        """Reject a pending submission."""
        pending = await self._claims.get_pending(pending_id)
        if pending is None:
            raise ValueError("pending_not_found")
        pending.processing_status = ProcessingStatus.rejected
        await self._log_action(
            actor_id=actor_id,
            action_type=ModerationActionType.reject_claim,
            target_type="pending_claim",
            target_id=pending_id,
            explanation=explanation,
            payload=None,
        )
