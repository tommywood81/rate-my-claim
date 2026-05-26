"""Public claim page: avoid repeating the same AI narrative twice."""

from __future__ import annotations

import re

from app.schemas.claims import AIAnalysisResponse

# Shown in the AI panel only when they add distinct information.
_PUBLIC_ANALYSIS_PRIORITY: tuple[str, ...] = (
    "structured_verdict",
    "confidence_analysis",
    "canonicalization_note",
    "canonicalization_rejected",
)


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed.rstrip(".")


def _texts_match(a: str | None, b: str | None) -> bool:
    na, nb = _normalize_text(a), _normalize_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 80 and longer.startswith(shorter[: min(len(shorter), 200)]):
        return True
    return False


def dedupe_public_ai_analyses(analyses: list[AIAnalysisResponse]) -> list[AIAnalysisResponse]:
    """
    Drop redundant confidence text when it duplicates the latest verdict summary.

    Preserves multiple structured_verdict rows (assessment history) when present.
    Input should be newest-first.
    """
    if not analyses:
        return []

    latest_verdict = next(
        (a for a in analyses if a.analysis_type == "structured_verdict"),
        None,
    )
    verdict_text = latest_verdict.generated_text if latest_verdict else None

    kept: list[AIAnalysisResponse] = []
    seen_confidence = False

    for row in analyses:
        if row.analysis_type == "confidence_analysis":
            if verdict_text and _texts_match(row.generated_text, verdict_text):
                continue
            if seen_confidence:
                continue
            seen_confidence = True
        kept.append(row)

    return kept[:24]
