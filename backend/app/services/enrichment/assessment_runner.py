"""Run confidence + verdict model stage according to pipeline AI config."""

from __future__ import annotations

from typing import Any

from app.core.enrichment_pipeline_config import AIStageConfig
from app.services.ai.providers.base import BaseAIProvider


def _split_combined_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split combined JSON into confidence scores dict and verdict dict."""
    scores_keys = {
        "aggregate",
        "evidence_quality",
        "source_credibility",
        "evidence_consistency",
        "freshness",
        "controversy_hint",
        "truth_label",
        "rationale",
    }
    scores = {k: payload[k] for k in scores_keys if k in payload}
    verdict = {
        "verdict_summary": payload.get("verdict_summary") or scores.get("rationale") or "",
        "citations": payload.get("citations") or [],
        "confidence_hint": float(
            payload.get("confidence_hint", scores.get("aggregate", 0.5)) or 0.5
        ),
        "controversy_hint": float(
            payload.get("controversy_hint", scores.get("controversy_hint", 0.0)) or 0.0
        ),
    }
    return scores, verdict


async def run_assessment_stage(
    provider: BaseAIProvider,
    *,
    claim: str,
    context: str,
    digest: str,
    has_corpus_evidence: bool,
    ai: AIStageConfig,
    provisional_verdict_from_scores,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Return (scores, verdict) for persistence as confidence_analysis + structured_verdict.

    Uses one combined call when configured and supported; otherwise sequential calls.
    """
    claim_in = claim[: ai.prompt_claim_max_chars]

    if ai.use_combined_assessment and has_corpus_evidence:
        combined_fn = getattr(provider, "generate_combined_assessment", None)
        if callable(combined_fn):
            payload = await combined_fn(claim_in, context, digest)
            return _split_combined_payload(payload)

    if has_corpus_evidence:
        scores = await provider.generate_confidence_analysis(claim_in, digest)
        verdict = await provider.structured_verdict(claim_in, context)
        return scores, verdict

    scores = await provider.generate_confidence_analysis(claim_in, digest)
    if ai.use_provisional_verdict_without_corpus:
        verdict = provisional_verdict_from_scores(scores)
    else:
        verdict = await provider.structured_verdict(claim_in, context)
    return scores, verdict


def resolve_research_summary(
    *,
    verdict: dict[str, Any],
    scores: dict[str, Any],
    has_corpus_evidence: bool,
    ai: AIStageConfig,
    fallback_from_scores,
) -> str:
    """Choose public ai_summary without an extra model call when configured."""
    if ai.skip_evidence_summary_call:
        summary = str(verdict.get("verdict_summary") or "").strip()
        if summary:
            return summary
        return fallback_from_scores(scores, has_corpus_evidence=has_corpus_evidence)
    return ""
