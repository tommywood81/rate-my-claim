"""Build live-claim UX fields for API responses from linked pending rows."""

from __future__ import annotations

from dataclasses import dataclass
from app.models.claim import Claim, PendingClaim, ProcessingStatus
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.schemas.claims import AIAnalysisResponse
from app.services.claims.live_summary import resolve_live_ai_summary
from app.services.claims.pipeline_labels import (
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
    moderation_reviewed: bool
    pending_ai_analyses: list[AIAnalysisResponse]


def _moderation_reviewed(pending: PendingClaim | None, claim: Claim) -> bool:
    if claim.last_reviewed_at is not None:
        return True
    if pending is None:
        return False
    return ProcessingStatus(str(pending.processing_status)) == ProcessingStatus.completed


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
    reviewed = _moderation_reviewed(pending, claim)
    vis = visibility_label(
        processing_status=proc,
        claim_status=str(claim.status),
        moderation_reviewed=reviewed,
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

    return ClaimLiveContext(
        processing_status=proc,
        pipeline_stage_key=pipeline_stage_key(proc),
        pipeline_stage_label=pipeline_stage_label(proc),
        live_ai_summary=live_summary,
        visibility_label=vis,
        moderation_reviewed=reviewed,
        pending_ai_analyses=pending_analyses,
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
