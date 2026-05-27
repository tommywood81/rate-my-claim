"""Submit-time duplicate blocking before enrichment is queued."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.ingestion.claim_normalization import (
    claim_submission_fingerprint,
    normalize_claim_text,
    normalized_texts_equivalent,
)
from app.services.ingestion.duplicate_detection_service import (
    DuplicateDetectionService,
    DuplicateMatch,
)


def test_claim_submission_fingerprint_is_case_insensitive() -> None:
    a = normalize_claim_text("Vitamin D reduces flu risk.")
    b = normalize_claim_text("vitamin d reduces flu risk.")
    assert claim_submission_fingerprint(a) == claim_submission_fingerprint(b)
    assert normalized_texts_equivalent(a, b)


@pytest.mark.asyncio
async def test_find_exact_normalized_duplicate_claim() -> None:
    session = MagicMock()
    svc = DuplicateDetectionService(session)
    claim = MagicMock()
    claim.id = uuid4()
    claim.public_slug = "vitamin-d-flu"
    claim.canonical_claim_text = "Vitamin D reduces flu risk."
    svc._claims = MagicMock()
    svc._claims.find_claim_by_normalized_submission_text = AsyncMock(return_value=claim)
    svc._claims.find_pending_by_normalized_submission_text = AsyncMock(return_value=None)

    match = await svc.find_exact_normalized_duplicate("Vitamin D reduces flu risk.")
    assert match is not None
    assert match.match_method == "exact"
    assert match.similarity == 1.0
    assert match.public_slug == "vitamin-d-flu"
    svc._claims.find_claim_by_normalized_submission_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_semantic_blocking_duplicate_prefers_highest_similarity_claim() -> None:
    session = MagicMock()
    svc = DuplicateDetectionService(session)
    claim_a = MagicMock()
    claim_a.id = uuid4()
    claim_a.public_slug = "claim-a"
    claim_a.canonical_claim_text = "Vitamin D reduces flu risk."
    claim_b = MagicMock()
    claim_b.id = uuid4()
    claim_b.public_slug = "claim-b"
    claim_b.canonical_claim_text = "Other claim."
    svc._claims = MagicMock()
    svc._claims.vector_similar_claims = AsyncMock(
        return_value=[(claim_a, 0.05), (claim_b, 0.20)]
    )
    svc._claims.vector_similar_pending = AsyncMock(return_value=[])
    svc._settings.duplicate_submit_block_threshold = 0.88

    match = await svc.find_semantic_blocking_duplicate([0.1] * 8)
    assert match is not None
    assert match.public_slug == "claim-a"
    assert match.match_method == "semantic"
    assert match.similarity == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_find_semantic_blocking_duplicate_returns_none_below_threshold() -> None:
    session = MagicMock()
    svc = DuplicateDetectionService(session)
    claim = MagicMock()
    claim.id = uuid4()
    claim.public_slug = "distant"
    claim.canonical_claim_text = "Unrelated."
    svc._claims = MagicMock()
    svc._claims.vector_similar_claims = AsyncMock(return_value=[(claim, 0.5)])
    svc._claims.vector_similar_pending = AsyncMock(return_value=[])
    svc._settings.duplicate_submit_block_threshold = 0.88

    assert await svc.find_semantic_blocking_duplicate([0.1] * 8) is None


@pytest.mark.asyncio
async def test_submit_block_threshold_stricter_than_enrichment_hints() -> None:
    """Submit hard-block default (0.88) catches paraphrases enrichment only hints at (0.92)."""
    session = MagicMock()
    svc = DuplicateDetectionService(session)
    claim = MagicMock()
    claim.id = uuid4()
    claim.public_slug = "vitamin-d-flu"
    claim.canonical_claim_text = "Vitamin D supplementation reduces seasonal flu risk in adults."
    svc._claims = MagicMock()
    svc._claims.vector_similar_claims = AsyncMock(return_value=[(claim, 0.10)])  # sim 0.90
    svc._claims.vector_similar_pending = AsyncMock(return_value=[])
    svc._settings.duplicate_submit_block_threshold = 0.88
    svc._settings.duplicate_vector_threshold = 0.92

    blocked = await svc.find_semantic_blocking_duplicate([0.1] * 8)
    assert blocked is not None

    hinted = await svc.find_blocking_duplicate([0.1] * 8)
    assert hinted is None


def test_duplicate_match_dataclass_fields() -> None:
    m = DuplicateMatch(
        public_slug="vitamin-d-flu",
        title="Vitamin D supplementation reduces flu.",
        similarity=0.96,
        match_kind="claim",
        match_method="semantic",
        claim_id=uuid4(),
    )
    assert m.public_slug == "vitamin-d-flu"
    assert m.match_method == "semantic"
