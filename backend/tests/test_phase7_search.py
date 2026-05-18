"""Phase 7: hybrid search ranking, cursors, and pagination."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.search.hybrid_ranking import (
    RankComponents,
    build_scored_claims,
    fuse_score,
    normalize_batch,
    safe_float,
)
from app.utils.search_cursor import SearchPageCursor, decode_search_cursor, encode_search_cursor

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 for Postgres search integration tests"


def test_safe_float_maps_nan_to_zero() -> None:
    assert safe_float(float("nan")) == 0.0
    assert safe_float(None) == 0.0


def test_normalize_batch_spreads_values() -> None:
    assert normalize_batch([0.0, 0.5, 1.0]) == [0.0, 0.5, 1.0]


def test_fuse_score_uses_weights() -> None:
    settings = Settings.model_construct(
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        hybrid_semantic_weight=0.35,
        hybrid_fts_weight=0.25,
        hybrid_evidence_weight=0.15,
        hybrid_confidence_weight=0.10,
        hybrid_freshness_weight=0.10,
        hybrid_relationship_weight=0.05,
    )
    components = RankComponents(
        semantic_similarity=1.0,
        text_relevance=1.0,
        evidence_quality=1.0,
        confidence_score=1.0,
        freshness_score=1.0,
        relationship_density=1.0,
    )
    assert abs(fuse_score(components, settings) - 1.0) < 1e-6


def test_build_scored_claims_orders_by_final_score() -> None:
    settings = Settings.model_construct(
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://u:p@localhost/db",
    )
    raw = [
        (uuid4(), 0.9, 0.1, 3, 0.8, 0.7, 2),
        (uuid4(), 0.2, 0.9, 1, 0.3, 0.4, 0),
    ]
    scored = build_scored_claims(raw, settings)
    assert len(scored) == 2
    assert scored[0].final_score >= 0


def test_search_cursor_roundtrip() -> None:
    key = "abc123"
    enc = encode_search_cursor(SearchPageCursor(offset=15, query_key=key))
    decoded = decode_search_cursor(enc)
    assert decoded is not None
    assert decoded.offset == 15
    assert decoded.query_key == key


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_search_endpoint_returns_scores_and_cursor(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hybrid search returns score breakdown and pagination meta (AI stubbed)."""
    from tests.test_claim_ai_analysis_flow import StubAIProvider

    monkeypatch.setattr(
        "app.services.search.claim_search_service.get_ai_provider",
        lambda **kwargs: StubAIProvider(),
    )
    res = await async_client.get("/api/v1/search/claims?q=health&limit=5")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("success") is True
    assert "has_more" in body.get("meta", {})
    if body.get("data"):
        assert "scores" in body["data"][0]
