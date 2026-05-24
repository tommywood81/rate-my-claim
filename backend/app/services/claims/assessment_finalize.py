"""Finalize pending enrichment onto the live claim (no human approval gate)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ClaimRevision, ClaimStatus, PendingClaim, ProcessingStatus
from app.models.evidence import Evidence, EvidenceSourceType, EvidenceStance
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.claims_repository import ClaimRepository
from app.services.ai.factory import get_ai_provider
from app.services.claims.claim_assessment import scores_from_pending_analyses
from app.services.claims.live_claim_sync import sync_pending_to_linked_claim

logger = logging.getLogger(__name__)

_RETRIEVAL_SOURCE = "assessment_finalize"
_IMPORT_TYPES = frozenset({"structured_verdict", "confidence_analysis"})


async def _replace_assessment_evidence(
    session: AsyncSession,
    *,
    claim: Claim,
    line_map: dict[int, dict],
    pending: PendingClaim,
    provider,
) -> int:
    """Persist archive/URL context lines used during enrichment as public evidence rows."""
    await session.execute(
        delete(Evidence).where(
            Evidence.claim_id == claim.id,
            Evidence.retrieval_source == _RETRIEVAL_SOURCE,
        )
    )
    added = 0
    now = datetime.now(tz=UTC)
    for _line_no, block in sorted(line_map.items()):
        kind = str(block.get("kind") or "")
        if kind == "url":
            title = str(block.get("title") or block.get("url") or "Source")
            url = str(block.get("url") or "") or None
            excerpt = str(block.get("text") or "")[:8000]
            ev = Evidence(
                claim_id=claim.id,
                source_type=EvidenceSourceType.user_submission.value,
                title=title[:512],
                url=url,
                publisher=str(block.get("publisher") or "")[:255] or None,
                summary=excerpt[:4000] if excerpt else None,
                cleaned_content=excerpt or None,
                stance=EvidenceStance.contextualizes.value,
                credibility_score=0.5,
                retrieval_timestamp=now,
                retrieval_source=_RETRIEVAL_SOURCE,
                created_by=pending.submitted_by,
            )
            session.add(ev)
            if excerpt:
                text_for_emb = f"{title}\n{excerpt}"[:8000]
                vec, emb_model = await provider.generate_embedding(text_for_emb)
                ev.embedding = vec
                ev.embedding_model = emb_model
                ev.embedding_version = pending.embedding_version
            added += 1
            continue
        if kind == "db_evidence":
            title = str(block.get("title") or "Archive match")
            excerpt = str(block.get("excerpt") or "")[:8000]
            ev = Evidence(
                claim_id=claim.id,
                source_type=EvidenceSourceType.api.value,
                title=title[:512],
                url=None,
                summary=excerpt[:4000] if excerpt else None,
                cleaned_content=excerpt or None,
                stance=EvidenceStance.contextualizes.value,
                credibility_score=0.45,
                retrieval_timestamp=now,
                retrieval_source=_RETRIEVAL_SOURCE,
                created_by=pending.submitted_by,
            )
            session.add(ev)
            added += 1
    return added


def _line_map_from_analyses(analyses) -> dict[int, dict]:
    for row in analyses:
        if row.analysis_type != "structured_verdict" or not row.structured_payload:
            continue
        try:
            bundle = json.loads(row.structured_payload)
        except json.JSONDecodeError:
            continue
        raw = bundle.get("line_map") or {}
        out: dict[int, dict] = {}
        for key, value in raw.items():
            try:
                out[int(key)] = value  # type: ignore[assignment]
            except (TypeError, ValueError):
                continue
        if out:
            return out
    return {}


async def finalize_pending_assessment(
    session: AsyncSession,
    pending_id: UUID,
    *,
    actor_id: UUID | None = None,
    created_by_job: str = "enrichment",
    explanation: str | None = None,
) -> Claim | None:
    """Promote enrichment output to the linked live claim and mark assessment complete."""
    repo = ClaimRepository(session)
    ai_repo = AIAnalysisRepository(session)
    pending = await repo.get_pending(pending_id)
    if pending is None or pending.linked_claim_id is None:
        return None

    claim = await repo.get_claim_by_id(pending.linked_claim_id)
    if claim is None or claim.deleted_at is not None:
        return None

    analyses = await ai_repo.list_for_target("pending_claim", pending_id)
    canonical = pending.canonical_candidate_text or pending.raw_claim_text
    confidence, controversy, evidence_quality = scores_from_pending_analyses(analyses)
    if analyses:
        claim.confidence_score = confidence
        claim.controversy_score = controversy
        claim.evidence_score = evidence_quality

    claim.canonical_claim_text = canonical
    claim.normalized_claim_text = pending.normalized_claim_text or canonical
    if pending.embedding is not None:
        claim.embedding = pending.embedding
        claim.embedding_model = pending.embedding_model
        claim.embedding_version = pending.embedding_version
        claim.embedding_at = pending.embedding_at

    line_map = _line_map_from_analyses(analyses)
    provider = get_ai_provider(budget_scope=f"finalize:{pending_id}")
    evidence_added = await _replace_assessment_evidence(
        session,
        claim=claim,
        line_map=line_map,
        pending=pending,
        provider=provider,
    )
    claim.evidence_count = evidence_added
    if evidence_added > 0:
        citation_score = min(1.0, 0.15 + 0.12 * evidence_added)
        claim.evidence_score = max(float(claim.evidence_score or 0.0), citation_score)
        if claim.status == ClaimStatus.insufficient_evidence.value:
            claim.status = ClaimStatus.weak_evidence.value
    elif analyses and claim.status == ClaimStatus.insufficient_evidence.value:
        claim.status = ClaimStatus.weak_evidence.value

    claim.last_reviewed_at = datetime.now(tz=UTC)
    pending.processing_status = ProcessingStatus.completed

    session.add(
        ClaimRevision(
            claim_id=claim.id,
            previous_status=None,
            new_status=str(claim.status),
            previous_confidence=None,
            new_confidence=claim.confidence_score,
            explanation=explanation or "Automated assessment published to live claim.",
            created_by=actor_id,
            created_at=datetime.now(tz=UTC),
        )
    )

    imported: set[str] = set()
    for row in analyses:
        if row.analysis_type not in _IMPORT_TYPES or row.analysis_type in imported:
            continue
        imported.add(row.analysis_type)
        payload = None
        if row.structured_payload:
            try:
                payload = json.loads(row.structured_payload)
            except json.JSONDecodeError:
                payload = None
        await ai_repo.add_analysis(
            target_type="claim",
            target_id=claim.id,
            model_name=row.model_name,
            provider=row.provider,
            analysis_type=row.analysis_type,
            generated_text=row.generated_text,
            structured_payload=payload,
            confidence=row.confidence,
            created_by_job=created_by_job,
        )

    await sync_pending_to_linked_claim(session, pending_id)
    await session.flush()
    logger.info(
        "assessment_finalized",
        extra={
            "claim_id": str(claim.id),
            "pending_id": str(pending_id),
            "evidence_added": evidence_added,
            "job": created_by_job,
        },
    )
    return claim
