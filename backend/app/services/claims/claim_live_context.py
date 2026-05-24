"""Build live-claim UX fields for API responses from linked pending rows."""

from __future__ import annotations

from dataclasses import dataclass
from app.models.claim import Claim, PendingClaim, ProcessingStatus
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.schemas.claims import AIAnalysisResponse
from app.services.claims.claim_assessment import truth_label_from_analyses
from app.services.claims.live_summary import resolve_live_ai_summary
from app.services.claims.pipeline_labels import (
    assessment_complete as pipeline_assessment_complete,
    pipeline_stage_key,
    pipeline_stage_label,
    visibility_label,
)
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ClaimLiveContext:
    """Extra fields for public claim pages while enrichment runs."""

    processing_status: str | None
    pipeline_stage_key: str | None
    pipeline_stage_label: str | None
    live_ai_summary: str | None
    visibility_label: str
    assessment_complete: bool
    moderation_reviewed: bool
    pending_ai_analyses: list[AIAnalysisResponse]
    truth_label: str | None


def _assessment_complete(pending: PendingClaim | None, claim: Claim) -> bool:
    if pending is not None and pipeline_assessment_complete(str(pending.processing_status)):
        return True
    return claim.last_reviewed_at is not None and bool(claim.embedding_at)


async def build_claim_live_context(
    session: AsyncSession,
    *,
    claim: Claim,
    pending: PendingClaim | None,
) -> ClaimLiveContext:
    """Derive pipeline and visibility semantics for a public claim."""
    proc = None
    if pending is not None:
        raw = pending.processing_status
        if isinstance(raw, ProcessingStatus):
            proc = raw.value
        else:
            text = str(raw)
            if text.startswith("ProcessingStatus."):
                text = text.split(".", 1)[1]
            proc = text
    complete = _assessment_complete(pending, claim)
    vis = visibility_label(
        processing_status=proc,
        claim_status=str(claim.status),
        evidence_count=int(claim.evidence_count or 0),
    )

    pending_analyses: list[AIAnalysisResponse] = []
    live_summary: str | None = None

    if pending is not None:
        ai_repo = AIAnalysisRepository(session)
        rows = await ai_repo.list_for_target("pending_claim", pending.id)
        seen: set[str] = set()
        for row in rows:
            if row.analysis_type in seen:
                continue
            seen.add(row.analysis_type)
            pending_analyses.append(AIAnalysisResponse.model_validate(row))
            if len(pending_analyses) >= 8:
                break
        live_summary = resolve_live_ai_summary(
            stored=pending.ai_summary,
            analyses=pending_analyses,
            canonical_claim_text=claim.canonical_claim_text,
        )
        truth_label = truth_label_from_analyses(pending_analyses, processing_status=proc)

    return ClaimLiveContext(
        processing_status=proc,
        pipeline_stage_key=pipeline_stage_key(proc),
        pipeline_stage_label=pipeline_stage_label(proc),
        live_ai_summary=live_summary,
        visibility_label=vis,
        assessment_complete=complete,
        moderation_reviewed=complete,
        pending_ai_analyses=pending_analyses,
        truth_label=truth_label,
    )


def merge_ai_analyses(
    claim_analyses: list[AIAnalysisResponse],
    pending_analyses: list[AIAnalysisResponse],
) -> list[AIAnalysisResponse]:
    """Prefer claim-stored analyses; fill gaps from pending enrichment."""
    seen = {a.analysis_type for a in claim_analyses}
    merged = list(claim_analyses)
    for row in pending_analyses:
        if row.analysis_type in seen:
            continue
        merged.append(row)
        seen.add(row.analysis_type)
    return merged[:12]
