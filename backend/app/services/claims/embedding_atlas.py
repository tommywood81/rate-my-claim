"""Project high-dimensional claim embeddings to 3D for the public atlas view."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Sequence
from uuid import UUID

import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ProcessingStatus
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.claims_repository import ClaimRepository
from app.services.claims.claim_assessment import truth_label_from_analyses


@dataclass(frozen=True)
class AtlasClaimRow:
    """Minimal claim fields needed for atlas projection and display."""

    id: UUID
    public_slug: str
    canonical_claim_text: str
    status: str
    confidence_score: float
    controversy_score: float
    evidence_score: float
    freshness_score: float
    evidence_count: int
    embedding: list[float]
    truth_label: str = "unclear"


@dataclass(frozen=True)
class AtlasPoint:
    """One claim positioned in 3D semantic space."""

    id: UUID
    public_slug: str
    label: str
    status: str
    confidence_score: float
    controversy_score: float
    evidence_score: float
    freshness_score: float
    evidence_count: int
    truth_label: str
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class AtlasProjection:
    """Full atlas payload assembled for the API."""

    points: list[AtlasPoint]
    method: str
    embedding_dimensions: int
    total_indexed: int
    projected_count: int
    computed_at: datetime


def _embedding_vector(raw: object) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [float(v) for v in raw]
    try:
        return [float(v) for v in list(raw)]
    except (TypeError, ValueError):
        return None


def rows_from_claims(claims: Sequence[Claim]) -> list[AtlasClaimRow]:
    """Build atlas rows from ORM claims, skipping rows without embeddings."""
    out: list[AtlasClaimRow] = []
    for claim in claims:
        vec = _embedding_vector(claim.embedding)
        if not vec:
            continue
        text = (claim.canonical_claim_text or "").strip()
        label = text if len(text) <= 120 else f"{text[:117]}…"
        out.append(
            AtlasClaimRow(
                id=claim.id,
                public_slug=claim.public_slug,
                canonical_claim_text=text,
                status=str(claim.status),
                confidence_score=float(claim.confidence_score),
                controversy_score=float(claim.controversy_score),
                evidence_score=float(claim.evidence_score),
                freshness_score=float(claim.freshness_score),
                evidence_count=int(claim.evidence_count),
                embedding=vec,
            )
        )
    return out


def _coerce_processing_status(value: ProcessingStatus | str) -> str:
    if isinstance(value, ProcessingStatus):
        return value.value
    text = str(value)
    if text.startswith("ProcessingStatus."):
        return text.split(".", 1)[1]
    return text


async def enrich_rows_with_truth_labels(
    session: AsyncSession,
    rows: list[AtlasClaimRow],
) -> list[AtlasClaimRow]:
    """Attach public truth banner labels for atlas coloring."""
    if not rows:
        return []
    from dataclasses import replace

    repo = ClaimRepository(session)
    ai_repo = AIAnalysisRepository(session)
    pending_map = await repo.pending_by_linked_claim_ids([r.id for r in rows])
    enriched: list[AtlasClaimRow] = []
    for row in rows:
        pending = pending_map.get(row.id)
        if pending is not None:
            proc = _coerce_processing_status(pending.processing_status)
            analyses = await ai_repo.list_for_target("pending_claim", pending.id)
        else:
            proc = "completed"
            analyses = await ai_repo.list_for_target("claim", row.id)
        truth = truth_label_from_analyses(
            analyses,
            processing_status=proc,
            evidence_count=row.evidence_count,
        )
        enriched.append(replace(row, truth_label=truth or "unclear"))
    return enriched


def project_to_3d(vectors: list[list[float]]) -> list[tuple[float, float, float]]:
    """
    PCA-style projection: center embeddings, take top 3 singular directions, scale to [-1, 1].
    """
    n = len(vectors)
    if n == 0:
        return []
    dim = len(vectors[0])
    matrix = np.array(vectors, dtype=np.float64)
    if matrix.shape[1] != dim:
        raise ValueError("inconsistent embedding dimensions")

    if n == 1:
        return [(0.0, 0.0, 0.0)]

    centered = matrix - matrix.mean(axis=0)
    if n == 2:
        # Two points: spread on first principal axis, zero depth.
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        axis = vt[0]
        coords = centered @ axis
        spread = float(np.max(np.abs(coords))) or 1.0
        return [
            (float(coords[0] / spread), 0.0, 0.0),
            (float(coords[1] / spread), 0.0, 0.0),
        ]

    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    k = min(3, vt.shape[0])
    components = vt[:k].T
    raw = centered @ components
    if k < 3:
        pad = np.zeros((n, 3 - k), dtype=np.float64)
        raw = np.hstack([raw, pad])

    scaled: list[tuple[float, float, float]] = []
    for row in raw[:, :3]:
        scaled.append((float(row[0]), float(row[1]), float(row[2])))

    arr = np.array(scaled, dtype=np.float64)
    for col in range(3):
        span = float(np.max(np.abs(arr[:, col])))
        if span > 1e-9:
            arr[:, col] /= span
    return [(float(r[0]), float(r[1]), float(r[2])) for r in arr]


def build_atlas_projection(rows: list[AtlasClaimRow]) -> AtlasProjection:
    """Project claim rows to 3D coordinates for visualization."""
    now = datetime.now(tz=UTC)
    if not rows:
        return AtlasProjection(
            points=[],
            method="pca_3d",
            embedding_dimensions=0,
            total_indexed=0,
            projected_count=0,
            computed_at=now,
        )

    dim = len(rows[0].embedding)
    coords = project_to_3d([r.embedding for r in rows])
    points = [
        AtlasPoint(
            id=row.id,
            public_slug=row.public_slug,
            label=row.canonical_claim_text[:120]
            if len(row.canonical_claim_text) <= 120
            else f"{row.canonical_claim_text[:117]}…",
            status=row.status,
            confidence_score=row.confidence_score,
            controversy_score=row.controversy_score,
            evidence_score=row.evidence_score,
            freshness_score=row.freshness_score,
            evidence_count=row.evidence_count,
            truth_label=row.truth_label,
            x=coord[0],
            y=coord[1],
            z=coord[2],
        )
        for row, coord in zip(rows, coords, strict=True)
    ]
    return AtlasProjection(
        points=points,
        method="pca_3d",
        embedding_dimensions=dim,
        total_indexed=len(rows),
        projected_count=len(points),
        computed_at=now,
    )
