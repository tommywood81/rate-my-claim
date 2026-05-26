"""On-demand structured verdict for an approved claim."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import Settings
from app.models.ai_analysis import AIAnalysis
from app.models.claim import Claim
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.services.ai.providers.base import BaseAIProvider


async def add_structured_verdict_for_claim(
    *,
    claim: Claim,
    provider: BaseAIProvider,
    ai_repo: AIAnalysisRepository,
    settings: Settings,
) -> AIAnalysis:
    """Build evidence context, call the provider, and persist ai_analysis for target_type=claim."""
    lines: list[str] = []
    for idx, ev in enumerate(claim.evidence_items or [], start=1):
        excerpt = (ev.summary or ev.cleaned_content or "")[:900]
        lines.append(f"{idx}. [evidence id={ev.id}] {ev.title}: {excerpt}")
    context = "\n".join(lines) if lines else "(no evidence attached to this claim)"
    verdict = await provider.structured_verdict(claim.canonical_claim_text, context)
    summary = str(verdict.get("verdict_summary") or "")
    conf_raw = verdict.get("confidence_hint")
    confidence = float(conf_raw) if conf_raw is not None else 0.5
    evidence_ids = [str(ev.id) for ev in (claim.evidence_items or [])]
    provenance = {
        "assessment_run_at": datetime.now(tz=UTC).isoformat(),
        "canonical_claim_text": claim.canonical_claim_text[:8000],
        "evidence_ids": evidence_ids,
        "created_by_job": "claim_detail_analysis",
    }
    return await ai_repo.add_analysis(
        target_type="claim",
        target_id=claim.id,
        model_name=settings.ai_model_reasoning,
        provider=provider.name,
        analysis_type="structured_verdict",
        generated_text=summary,
        structured_payload={"verdict": verdict, "provenance": provenance},
        confidence=confidence,
        created_by_job="claim_detail_analysis",
    )
