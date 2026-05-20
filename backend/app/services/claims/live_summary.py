"""Resolve public research summary text for live claims."""

from __future__ import annotations

from app.schemas.claims import AIAnalysisResponse

_STALE_SUMMARY_MARKERS: tuple[str, ...] = (
    "Claim requires moderator review (automatic rejection hint).",
    "automatic rejection hint",
)

_SUMMARY_TYPE_PRIORITY: tuple[str, ...] = (
    "confidence_analysis",
    "structured_verdict",
    "canonicalization_note",
    "canonicalization_rejected",
)


def is_stale_live_summary(text: str | None) -> bool:
    """True when stored pending.ai_summary should not be shown as research summary."""
    if not text or not text.strip():
        return True
    lowered = text.strip().lower()
    return any(marker.lower() in lowered for marker in _STALE_SUMMARY_MARKERS)


def resolve_live_ai_summary(
    *,
    stored: str | None,
    analyses: list[AIAnalysisResponse],
    canonical_claim_text: str,
) -> str | None:
    """Prefer stored summary unless stale; otherwise use newest enrichment analyses."""
    if stored and not is_stale_live_summary(stored):
        return stored.strip()

    by_type: dict[str, AIAnalysisResponse] = {}
    for row in analyses:
        if row.analysis_type not in by_type:
            by_type[row.analysis_type] = row

    for analysis_type in _SUMMARY_TYPE_PRIORITY:
        row = by_type.get(analysis_type)
        if row is None:
            continue
        text = (row.generated_text or "").strip()
        if not text:
            continue
        if analysis_type in {"canonicalization_note", "canonicalization_rejected"}:
            claim = canonical_claim_text.strip()
            if claim and claim.lower() not in text.lower():
                return f"{claim} — {text}"
            return text
        return text

    if stored and stored.strip():
        return stored.strip()
    return None
