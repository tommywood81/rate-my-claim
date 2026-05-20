"""Enrichment cross-claim retrieval guards."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.repositories.claims_repository import ClaimRepository
from app.schemas.claims import AIAnalysisResponse
from app.services.claims.ai_analyses_display import dedupe_public_ai_analyses
from app.services.claims.live_summary import is_stale_live_summary, resolve_live_ai_summary
from app.workers.tasks.enrichment_tasks import (
    _provisional_verdict_from_scores,
    _research_summary_from_scores,
)
from datetime import UTC, datetime
from uuid import uuid4


def test_dedupe_public_ai_analyses_hides_duplicate_confidence_text() -> None:
    text = (
        "The claim that there are 8 planets in our solar system is widely accepted "
        "and supported by astronomical research."
    )
    analyses = [
        AIAnalysisResponse(
            id=uuid4(),
            analysis_type="structured_verdict",
            model_name="gpt-4o-mini",
            provider="openai",
            generated_text=text,
            structured_payload=None,
            created_at=datetime.now(tz=UTC),
        ),
        AIAnalysisResponse(
            id=uuid4(),
            analysis_type="confidence_analysis",
            model_name="gpt-4o-mini",
            provider="openai",
            generated_text=text,
            structured_payload=None,
            created_at=datetime.now(tz=UTC),
        ),
    ]
    out = dedupe_public_ai_analyses(analyses)
    assert len(out) == 1
    assert out[0].analysis_type == "structured_verdict"


def test_resolve_live_summary_replaces_stale_rejection_hint() -> None:
    stale = "Claim requires moderator review (automatic rejection hint)."
    assert is_stale_live_summary(stale)
    analyses = [
        AIAnalysisResponse(
            id=uuid4(),
            analysis_type="canonicalization_rejected",
            model_name="gpt-4o-mini",
            provider="openai",
            generated_text="The claim is false and can be empirically tested.",
            structured_payload=None,
            created_at=datetime.now(tz=UTC),
        )
    ]
    out = resolve_live_ai_summary(
        stored=stale,
        analyses=analyses,
        canonical_claim_text="the stars in the sky are all the same size",
    )
    assert "stars in the sky" in out
    assert "false" in out.lower()
    assert "rejection hint" not in out.lower()


def test_provisional_summary_uses_confidence_rationale() -> None:
    scores = {
        "aggregate": 0.9,
        "rationale": "Gold is denser than copper by volume.",
    }
    assert "Gold is denser" in _research_summary_from_scores(scores, has_corpus_evidence=False)
    verdict = _provisional_verdict_from_scores(scores)
    assert verdict["verdict_summary"] == scores["rationale"]
    assert verdict["citations"] == []


def test_similarity_floor_filters_weak_neighbors() -> None:
    """Only neighbors above min_similarity should contribute claim ids."""
    # distance 0.35 -> similarity 0.65 (below 0.72)
    # distance 0.20 -> similarity 0.80 (above 0.72)
    neighbors = [
        (uuid4(), 0.35),
        (uuid4(), 0.20),
    ]
    min_sim = 0.72
    selected = [cid for cid, dist in neighbors if (1.0 - dist) >= min_sim]
    assert len(selected) == 1


@pytest.mark.asyncio
async def test_evidence_for_similar_claims_empty_when_all_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No evidence rows when every vector neighbor is below the similarity floor."""

    class _Session:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("should not query evidence when no similar claims")

    repo = ClaimRepository(_Session())  # type: ignore[arg-type]

    async def _fake_similar(_embedding, *, limit, exclude_id=None):
        from app.models.claim import Claim

        claim = Claim(
            id=uuid4(),
            public_slug="seed-exercise",
            canonical_claim_text="Exercise helps the heart.",
            normalized_claim_text="Exercise helps the heart.",
            status="weak_evidence",
        )
        return [(claim, 0.40)]  # similarity 0.60

    monkeypatch.setattr(repo, "vector_similar_claims", _fake_similar)
    out = await repo.evidence_for_similar_claims(
        [0.0] * 8,
        limit=10,
        min_similarity=0.72,
    )
    assert out == []


@pytest.mark.asyncio
async def test_duplicate_detection_excludes_linked_live_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live claim created from pending must not appear as its own duplicate."""
    from uuid import UUID

    from app.services.ingestion.duplicate_detection_service import DuplicateDetectionService

    linked_id = uuid4()
    pending_id = uuid4()

    class _Session:
        pass

    svc = DuplicateDetectionService(_Session())  # type: ignore[arg-type]

    async def _fake_claims(_embedding, *, limit, exclude_id=None):
        from app.models.claim import Claim

        self_claim = Claim(
            id=linked_id,
            public_slug="darth-vader-is-evil-abc",
            canonical_claim_text="Darth Vader is evil",
            normalized_claim_text="Darth Vader is evil",
            status="insufficient_evidence",
        )
        return [(self_claim, 0.01)]

    async def _fake_pending(_embedding, *, limit, exclude_id=None):
        return []

    monkeypatch.setattr(svc._claims, "vector_similar_claims", _fake_claims)
    monkeypatch.setattr(svc._claims, "vector_similar_pending", _fake_pending)

    out = await svc.find_duplicate_candidate_ids(
        [0.0] * 8,
        pending_id=pending_id,
        exclude_claim_id=linked_id,
    )
    assert out == []
