"""Embedding atlas projection tests."""

from __future__ import annotations

from uuid import uuid4

import numpy as np

from app.services.claims.embedding_atlas import (
    AtlasClaimRow,
    build_atlas_projection,
    project_to_3d,
)


def test_project_to_3d_spreads_well_separated_clusters() -> None:
    rng = np.random.default_rng(42)
    dim = 32
    centers = [np.zeros(dim), np.zeros(dim), np.zeros(dim)]
    centers[0][0] = 8.0
    centers[1][1] = 8.0
    centers[2][2] = 8.0
    clusters = [rng.normal(loc=c, scale=0.02, size=(4, dim)) for c in centers]
    vectors = [row.tolist() for block in clusters for row in block]
    coords = np.array(project_to_3d(vectors))
    assert coords.shape == (12, 3)
    spans = [float(coords[:, i].max() - coords[:, i].min()) for i in range(3)]
    assert sum(spans) > 0.5


def test_build_atlas_projection_empty() -> None:
    out = build_atlas_projection([])
    assert out.points == []
    assert out.total_indexed == 0


def test_build_atlas_projection_single_point_at_origin() -> None:
    row = AtlasClaimRow(
        id=uuid4(),
        public_slug="silver-platinum",
        canonical_claim_text="silver is more expensive than platinum",
        status="insufficient_evidence",
        confidence_score=0.5,
        controversy_score=0.0,
        evidence_score=0.1,
        freshness_score=0.5,
        evidence_count=0,
        embedding=[0.1] * 8,
    )
    out = build_atlas_projection([row])
    assert len(out.points) == 1
    assert out.points[0].x == 0.0
    assert out.points[0].y == 0.0
    assert out.points[0].z == 0.0
    assert out.points[0].truth_label == "unclear"
