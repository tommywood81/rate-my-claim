"""Hybrid ranking fusion per product spec."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.config import Settings


def safe_float(value: object, default: float = 0.0) -> float:
    """Coerce to float; map None/NaN/inf to default for JSON-safe scores."""
    try:
        n = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if math.isnan(n) or math.isinf(n):
        return default
    return n


@dataclass(frozen=True)
class RankComponents:
    """Raw and normalized ranking signals for one claim."""

    semantic_similarity: float
    text_relevance: float
    evidence_quality: float
    confidence_score: float
    freshness_score: float
    relationship_density: float


@dataclass(frozen=True)
class ScoredClaim:
    """Claim with fused relevance score and component breakdown."""

    claim_id: str
    final_score: float
    components: RankComponents


def normalize_batch(values: list[float]) -> list[float]:
    """Min-max normalize a batch to [0, 1]; constant batch -> 1.0 if any positive else 0."""
    cleaned = [safe_float(v) for v in values]
    if not cleaned:
        return []
    lo = min(cleaned)
    hi = max(cleaned)
    if hi <= lo:
        return [1.0 if hi > 0 else 0.0 for _ in cleaned]
    return [(v - lo) / (hi - lo) for v in cleaned]


def fuse_score(components: RankComponents, settings: Settings) -> float:
    """Apply weighted hybrid formula from spec."""
    return safe_float(
        settings.hybrid_semantic_weight * components.semantic_similarity
        + settings.hybrid_fts_weight * components.text_relevance
        + settings.hybrid_evidence_weight * components.evidence_quality
        + settings.hybrid_confidence_weight * components.confidence_score
        + settings.hybrid_freshness_weight * components.freshness_score
        + settings.hybrid_relationship_weight * components.relationship_density
    )


def build_scored_claims(
    raw_rows: list[tuple],
    settings: Settings,
) -> list[ScoredClaim]:
    """Normalize batch signals and compute final scores.

    Each raw row: (claim_id, vec_sim, fts_raw, evidence_count, confidence, freshness, rel_count)
    """
    if not raw_rows:
        return []
    vec_sims = [safe_float(r[1]) for r in raw_rows]
    fts_raw = [safe_float(r[2]) for r in raw_rows]
    norm_fts = normalize_batch(fts_raw)
    norm_sem = normalize_batch(vec_sims)

    scored: list[ScoredClaim] = []
    for i, row in enumerate(raw_rows):
        claim_id, _, _, ev_count, confidence, freshness, rel_count = row
        ev_q = min(1.0, float(ev_count or 0) / 6.0)
        rel_d = min(1.0, float(rel_count or 0) / 8.0)
        components = RankComponents(
            semantic_similarity=norm_sem[i],
            text_relevance=norm_fts[i],
            evidence_quality=ev_q,
            confidence_score=min(1.0, max(0.0, float(confidence or 0))),
            freshness_score=min(1.0, max(0.0, float(freshness or 0))),
            relationship_density=rel_d,
        )
        scored.append(
            ScoredClaim(
                claim_id=str(claim_id),
                final_score=fuse_score(components, settings),
                components=components,
            )
        )
    return scored
