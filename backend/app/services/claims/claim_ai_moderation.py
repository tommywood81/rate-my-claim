"""Moderator on-demand AI analysis eligibility and timestamps."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.ai_analysis import AIAnalysis
from app.models.claim import Claim
from app.repositories.ai_analysis_repository import AIAnalysisRepository

STUB_PROVIDER = "stub"


def claim_has_attached_evidence(claim: Claim) -> bool:
    """True when the claim has evidence rows moderators can cite."""
    if claim.evidence_items:
        return True
    return int(claim.evidence_count or 0) > 0


def analyses_use_stub_provider(analyses: list[AIAnalysis]) -> bool:
    """True when any stored analysis was produced by the test stub provider."""
    return any(str(row.provider).lower() == STUB_PROVIDER for row in analyses)


def latest_analysis_at(analyses: list[AIAnalysis]) -> datetime | None:
    """Newest created_at across analysis rows, if any."""
    if not analyses:
        return None
    return max(row.created_at for row in analyses)


async def collect_claim_ai_context(
    ai_repo: AIAnalysisRepository,
    *,
    claim_id: UUID,
    pending_id: UUID | None,
) -> tuple[list[AIAnalysis], datetime | None]:
    """Load claim + pending analyses and derive last AI run time."""
    claim_rows = await ai_repo.list_for_target("claim", claim_id)
    pending_rows: list[AIAnalysis] = []
    if pending_id is not None:
        pending_rows = await ai_repo.list_for_target("pending_claim", pending_id)
    combined = claim_rows + pending_rows
    return combined, latest_analysis_at(combined)


def on_demand_analysis_block_reason(
    *,
    claim: Claim,
    analyses: list[AIAnalysis],
) -> str | None:
    """Return a machine reason when on-demand analysis must not run."""
    if not claim_has_attached_evidence(claim):
        return "no_evidence"
    if analyses_use_stub_provider(analyses):
        return "stub_provider"
    return None


def on_demand_analysis_available(*, claim: Claim, analyses: list[AIAnalysis]) -> bool:
    """Whether moderators may trigger POST /claims/{slug}/ai-analysis."""
    return on_demand_analysis_block_reason(claim=claim, analyses=analyses) is None
