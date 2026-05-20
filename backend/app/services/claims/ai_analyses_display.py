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
    # Treat long shared prefix as duplicate (model copy-paste between fields).
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 80 and longer.startswith(shorter[: min(len(shorter), 200)]):
        return True
    return False


def dedupe_public_ai_analyses(analyses: list[AIAnalysisResponse]) -> list[AIAnalysisResponse]:
    """Drop analyses whose narrative duplicates a higher-priority entry."""
    by_type = {a.analysis_type: a for a in analyses}
    verdict = by_type.get("structured_verdict")
    verdict_text = verdict.generated_text if verdict else None

    kept: list[AIAnalysisResponse] = []
    skipped_types: set[str] = set()

    for analysis_type in _PUBLIC_ANALYSIS_PRIORITY:
        row = by_type.get(analysis_type)
        if row is None:
            continue
        if analysis_type == "confidence_analysis" and verdict_text:
            if _texts_match(row.generated_text, verdict_text):
                skipped_types.add(analysis_type)
                continue
        kept.append(row)

    seen = {a.analysis_type for a in kept} | skipped_types
    for row in analyses:
        if row.analysis_type in seen:
            continue
        kept.append(row)
        seen.add(row.analysis_type)

    return kept[:12]
