"""POST claim AI analysis and assert it appears on claim detail (opt-in integration)."""

from __future__ import annotations

import os
from typing import Any

import pytest
from httpx import AsyncClient

from app.services.ai.providers.base import BaseAIProvider

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = (
    "Set RUN_PG_INTEGRATION=1 with DATABASE_URL (asyncpg) and Redis; "
    "OPENAI_API_KEY not required when this test stubs the AI provider"
)


class StubAIProvider(BaseAIProvider):
    """Deterministic provider so OpenAI is not required for this test."""

    name = "stub"

    async def generate_embedding(self, text: str) -> tuple[list[float], str]:
        return [0.0] * 1536, "stub-emb"

    async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
        return {"canonical_text": raw_text, "normalized_text": raw_text.lower()}

    async def summarize_evidence(self, context: str) -> str:
        return "stub summary"

    async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
        return "contextualizes"

    async def detect_duplicates_llm(self, claim: str, candidates: list[str]) -> list[int]:
        return []

    async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
        return "stub"

    async def generate_confidence_analysis(
        self,
        claim: str,
        evidence_digest: str,
    ) -> dict[str, Any]:
        return {"aggregate": 0.5, "rationale": "stub"}

    async def structured_verdict(
        self,
        claim: str,
        retrieved_context: str,
    ) -> dict[str, Any]:
        summary = (
            "Stub verdict: evidence context supports a cautious reading of the claim."
        )
        return {
            "verdict_summary": summary,
            "confidence_hint": 0.77,
        }


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_moderator_post_ai_analysis_appears_on_detail(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Moderator triggers analysis; detail returns the new row (AI provider stubbed)."""
    monkeypatch.setattr(
        "app.api.v1.routes.claims.get_ai_provider",
        lambda **kwargs: StubAIProvider(),
    )
    password = os.environ.get("SEED_PASSWORD", "SeedDev!ChangeMe123")
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "seed_moderator", "password": password},
    )
    assert login.status_code == 200, login.text
    csrf = login.cookies.get("rmc_csrf", "")

    listed = await async_client.get("/api/v1/claims?limit=1")
    assert listed.status_code == 200, listed.text
    rows = listed.json().get("data") or []
    if not rows:
        pytest.skip("No claims in database; run scripts/seed_development.py first")
    slug = rows[0]["public_slug"]

    before = await async_client.get(f"/api/v1/claims/{slug}")
    assert before.status_code == 200
    n_before = len(before.json().get("data", {}).get("ai_analyses", []))

    posted = await async_client.post(
        f"/api/v1/claims/{slug}/ai-analysis",
        headers={"X-CSRF-Token": csrf} if csrf else {},
    )
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert body["success"] is True
    assert "Stub verdict" in body["data"]["generated_text"]

    after = await async_client.get(f"/api/v1/claims/{slug}")
    assert after.status_code == 200
    analyses = after.json().get("data", {}).get("ai_analyses", [])
    assert len(analyses) == n_before + 1
    assert analyses[0]["analysis_type"] == "structured_verdict"
