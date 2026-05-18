"""Phase 6: evidence ingestion, chunking, deduplication, and semantic retrieval."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.evidence.chunking import chunk_text
from app.services.evidence.citations import extract_citations
from app.services.evidence.deduplication import content_hash, normalize_url
from app.services.evidence.html_extractor import ExtractedDocument, HtmlExtractor
from app.services.evidence.ingestion_service import EvidenceIngestionService

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 with Postgres/Redis for integration tests"


def test_normalize_url_strips_fragment() -> None:
    assert normalize_url("https://Example.com/path/") == normalize_url("https://example.com/path")


def test_content_hash_stable() -> None:
    h1 = content_hash(url="https://a.com/x", text="hello")
    h2 = content_hash(url="https://a.com/x", text="hello")
    assert h1 == h2
    assert h1 != content_hash(url="https://a.com/x", text="world")


def test_chunk_text_splits_long_body() -> None:
    body = "word " * 800
    chunks = chunk_text(body, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_extract_citations_finds_doi_and_url() -> None:
    text = "See https://example.org/paper and doi:10.1038/nature12373 for details."
    cites = extract_citations(text)
    kinds = {c["kind"] for c in cites}
    assert "url" in kinds
    assert "doi" in kinds


@pytest.mark.asyncio
async def test_ingestion_service_persists_artifact_with_mocked_extract() -> None:
    """Ingest URL using mocked HTML extraction and AI provider."""
    if _SKIP:
        pytest.skip(_SKIP_REASON)

    from app.db.session import AsyncSessionLocal
    from app.services.ai.providers.base import BaseAIProvider

    class StubAI(BaseAIProvider):
        name = "stub"

        async def generate_embedding(self, text: str) -> tuple[list[float], str]:
            return [0.0] * 1536, "stub"

        async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
            return {}

        async def summarize_evidence(self, context: str) -> str:
            return ""

        async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
            return "contextualizes"

        async def detect_duplicates(self, claim: str, candidates: list[str]) -> list[int]:
            return []

        async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
            return ""

        async def generate_confidence_analysis(
            self, claim: str, evidence_digest: str
        ) -> dict[str, Any]:
            return {}

        async def structured_verdict(self, claim: str, retrieved_context: str) -> dict[str, Any]:
            return {}

    doc = ExtractedDocument(
        url="https://example.com/article",
        title="Example Article",
        text="Vitamin D may support immune function in adults. " * 20,
        publisher="example.com",
        authors="Jane Doe",
        publication_date=datetime.now(tz=UTC),
        citations=[{"kind": "url", "value": "https://example.com/ref"}],
        retrieval_source="test",
    )
    extractor = HtmlExtractor()
    extractor.extract = AsyncMock(return_value=doc)  # type: ignore[method-assign]

    url = f"https://example.com/article-{uuid4().hex[:8]}"
    doc.url = url

    async with AsyncSessionLocal() as session:
        svc = EvidenceIngestionService(session, extractor=extractor)
        artifact = await svc.ingest_url(
            url,
            source_type="manual_url",
            provider=StubAI(),
            budget_scope="test",
        )
        await session.commit()

    assert artifact.url == normalize_url(url)
    assert artifact.cleaned_content
    assert artifact.retrieval_timestamp
    assert artifact.retrieval_source
    assert artifact.citations
    assert len(artifact.chunks or []) >= 1


@pytest.mark.asyncio
async def test_semantic_search_returns_hits() -> None:
    """Stored chunks are retrievable by semantic search."""
    if _SKIP:
        pytest.skip(_SKIP_REASON)

    from app.db.session import AsyncSessionLocal
    from app.services.evidence.semantic_retrieval import EvidenceSemanticRetrieval

    class StubAI:
        name = "stub"

        async def generate_embedding(self, text: str) -> tuple[list[float], str]:
            if "immune" in text.lower():
                return [1.0] + [0.0] * 1535, "stub"
            return [0.0] * 1536, "stub"

    query = "immune function adults"
    async with AsyncSessionLocal() as session:
        from app.services.evidence.ingestion_service import EvidenceIngestionService
        from app.services.ai.providers.base import BaseAIProvider

        class FullStub(BaseAIProvider):
            name = "stub"

            async def generate_embedding(self, text: str) -> tuple[list[float], str]:
                return await StubAI().generate_embedding(text)

            async def canonicalize_claim(self, raw_text: str) -> dict[str, Any]:
                return {}

            async def summarize_evidence(self, context: str) -> str:
                return ""

            async def classify_stance(self, claim: str, evidence_excerpt: str) -> str:
                return "contextualizes"

            async def detect_duplicates(self, claim: str, candidates: list[str]) -> list[int]:
                return []

            async def analyze_contradictions(self, claim: str, evidence_blocks: str) -> str:
                return ""

            async def generate_confidence_analysis(
                self, claim: str, evidence_digest: str
            ) -> dict[str, Any]:
                return {}

            async def structured_verdict(self, claim: str, retrieved_context: str) -> dict[str, Any]:
                return {}

        doc = ExtractedDocument(
            url=f"https://example.com/immune-{uuid4().hex[:8]}",
            title="Immune study",
            text="Vitamin D supports immune function in adults during winter.",
            publisher="example",
            authors=None,
            publication_date=None,
        )
        extractor = HtmlExtractor()
        extractor.extract = AsyncMock(return_value=doc)  # type: ignore[method-assign]

        svc = EvidenceIngestionService(session, extractor=extractor)
        await svc.ingest_url(doc.url, provider=FullStub(), budget_scope="search_test")
        await session.commit()

        retrieval = EvidenceSemanticRetrieval(session)
        with patch(
            "app.services.evidence.semantic_retrieval.get_ai_provider",
            return_value=FullStub(),
        ):
            hits = await retrieval.search(query, limit=5, budget_scope="test")
        assert hits
        assert hits[0].artifact_url
