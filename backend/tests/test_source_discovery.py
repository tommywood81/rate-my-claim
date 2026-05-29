"""Tests for reputable source discovery during enrichment."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.enrichment_pipeline_config import SourceDiscoveryConfig
from app.services.enrichment.discovery_queries import build_discovery_queries
from app.services.enrichment.excerpt_utils import (
    excerpt_claim_overlap,
    excerpt_meets_relevance,
    pick_keyword_window_excerpt,
    pick_relevant_excerpt,
)
from app.services.enrichment.reputable_allowlist import (
    clear_allowlist_cache,
    is_allowlisted_url,
    load_allowlisted_publishers,
    match_allowlisted_publisher,
)
from app.services.enrichment.source_discovery import (
    ReputableSourceHit,
    discover_reputable_sources,
    hits_to_url_blocks,
)
from app.services.enrichment.web_search import (
    StaticUrlSearch,
    _parse_ddg_html,
    wikipedia_query_variants,
)
from app.services.evidence.html_extractor import ExtractedDocument


@pytest.fixture(autouse=True)
def _clear_allowlist() -> None:
    clear_allowlist_cache()
    yield
    clear_allowlist_cache()


def test_pick_relevant_excerpt_prefers_claim_overlap() -> None:
    claim = "Frogs are usually green amphibians"
    text = (
        "Bananas are yellow fruits grown in tropical regions. "
        "Many frog species have green skin used for camouflage among leaves. "
        "Stock markets open on weekdays."
    )
    excerpt = pick_relevant_excerpt(text, claim, max_chars=200)
    assert "frog" in excerpt.lower()
    assert "banana" not in excerpt.lower()


def test_allowlist_matches_subdomains() -> None:
    allowlist = load_allowlisted_publishers("config/reputable_sources.yaml")
    assert allowlist
    match = match_allowlisted_publisher("https://www.nih.gov/news/example", allowlist)
    assert match is not None
    assert match.publisher == "NIH"
    assert is_allowlisted_url("https://example.com/page", allowlist) is False


def test_hits_to_url_blocks_shape() -> None:
    from app.services.enrichment.source_discovery import ReputableSourceHit

    hit = ReputableSourceHit(
        url="https://www.nih.gov/example",
        title="NIH article",
        publisher="NIH",
        excerpt="Frogs are often green.",
        credibility_score=0.9,
        retrieved_at=datetime(2026, 5, 29, tzinfo=UTC),
    )
    blocks = hits_to_url_blocks([hit])
    assert len(blocks) == 1
    assert blocks[0]["url"] == hit.url
    assert blocks[0]["source_channel"] == "reputable_web"
    assert blocks[0]["text"] == hit.excerpt


@pytest.mark.asyncio
async def test_discover_reputable_sources_fetches_allowlisted_hits() -> None:
    cfg = SourceDiscoveryConfig(
        enabled=True,
        max_sources=3,
        excerpt_max_chars=200,
        min_publisher_credibility=0.70,
        allowlist_config_path="config/reputable_sources.yaml",
    )
    search = StaticUrlSearch(
        [
            "https://www.nih.gov/health/frog-color",
            "https://untrusted.example.org/spam",
            "https://www.cdc.gov/frogs/overview",
        ]
    )

    class _Extractor:
        async def extract(self, url: str) -> ExtractedDocument:
            return ExtractedDocument(
                url=url,
                title="Frog colors",
                text="Many frogs are green. Some tropical frogs use bright colors as a warning.",
                publisher="NIH" if "nih" in url else "CDC",
                authors=None,
                publication_date=None,
            )

    hits = await discover_reputable_sources(
        "Frogs are usually green",
        cfg=cfg,
        extractor=_Extractor(),
        search=search,
    )
    assert len(hits) == 2
    urls = {h.url for h in hits}
    assert "https://www.nih.gov/health/frog-color" in urls
    assert "https://www.cdc.gov/frogs/overview" in urls
    assert all(h.excerpt for h in hits)
    assert all(h.credibility_score >= 0.70 for h in hits)


@pytest.mark.asyncio
async def test_discover_returns_empty_when_search_fails() -> None:
    cfg = SourceDiscoveryConfig(enabled=True, max_sources=3)
    search = StaticUrlSearch([])
    hits = await discover_reputable_sources("anything", cfg=cfg, search=search)
    assert hits == []


@pytest.mark.asyncio
async def test_build_evidence_context_includes_reputable_blocks() -> None:
    from app.core.enrichment_pipeline_config import RetrievalStageConfig
    from app.services.enrichment.context_builder import build_evidence_context

    blocks = hits_to_url_blocks(
        [
            ReputableSourceHit(
                url="https://www.nih.gov/x",
                title="NIH",
                publisher="NIH",
                excerpt="Frogs are green.",
                credibility_score=0.9,
                retrieved_at=datetime.now(tz=UTC),
            )
        ]
    )
    bundle = build_evidence_context(
        evidence_rows=[],
        url_blocks=blocks,
        retrieval=RetrievalStageConfig(),
        empty_digest_prompt="empty",
    )
    assert bundle.has_corpus_evidence is True
    assert len(bundle.line_map) == 1
    assert bundle.line_map[1]["url"] == "https://www.nih.gov/x"


def test_parse_ddg_html_reads_result_links() -> None:
    html = (
        '<a class="result__a" href="https://en.wikipedia.org/wiki/Blue_whale">Blue whale</a>'
        '<a class="result__a" href="https://example.com/spam">Spam</a>'
    )
    urls = _parse_ddg_html(html, limit=5)
    assert urls == [
        "https://en.wikipedia.org/wiki/Blue_whale",
        "https://example.com/spam",
    ]


def test_build_discovery_queries_includes_price_focus() -> None:
    variants = build_discovery_queries("Lithium is more expensive than silver.")
    assert "Lithium is more expensive than silver." in variants
    assert any("price" in v.lower() for v in variants)
    assert any("britannica.com" in v for v in variants)


def test_excerpt_meets_relevance_rejects_rhodium_only() -> None:
    claim = "Lithium is more expensive than silver."
    assert (
        excerpt_meets_relevance(
            "Rhodium and iridium are the most expensive elements.",
            claim,
            min_overlap=1,
        )
        is False
    )
    assert excerpt_meets_relevance(
        "Lithium costs more than silver per ounce.", claim, min_overlap=1
    )


def test_keyword_window_finds_entity_in_page() -> None:
    text = "Intro paragraph. " * 5 + "Lithium prices surged in 2022 while industrial demand grew."
    claim = "Lithium is more expensive than silver."
    window = pick_keyword_window_excerpt(text, claim, max_chars=120)
    assert "lithium" in window.lower()
    assert excerpt_claim_overlap(window, claim) >= 1


def test_wikipedia_query_variants_shortens_long_claims() -> None:
    variants = wikipedia_query_variants("The blue whale is the largest fish")
    assert "The blue whale is the largest fish" in variants
    assert "blue whale largest fish" in variants
    assert "blue whale" in variants


@pytest.mark.asyncio
async def test_discover_reputable_sources_live_wikipedia_fallback() -> None:
    """Integration: multi-query discovery finds allowlisted pages for factual claims."""
    cfg = SourceDiscoveryConfig(
        enabled=True,
        max_sources=2,
        excerpt_max_chars=300,
        min_publisher_credibility=0.70,
        min_excerpt_keyword_overlap=1,
        max_urls_per_domain=2,
        max_candidate_fetches=8,
        search_result_limit=10,
        allowlist_config_path="config/reputable_sources.yaml",
    )
    hits = await discover_reputable_sources(
        "The blue whale is the largest fish",
        cfg=cfg,
    )
    assert len(hits) >= 1
    assert all(h.excerpt for h in hits)
    assert all(h.url.startswith("https://") for h in hits)
    claim = "The blue whale is the largest fish"
    assert all(excerpt_claim_overlap(h.excerpt, claim) >= 1 for h in hits)


@pytest.mark.asyncio
async def test_discover_skips_irrelevant_excerpt() -> None:
    cfg = SourceDiscoveryConfig(
        enabled=True,
        max_sources=2,
        min_excerpt_keyword_overlap=1,
        allowlist_config_path="config/reputable_sources.yaml",
    )

    class _Extractor:
        async def extract(self, url: str):
            from app.services.evidence.html_extractor import ExtractedDocument

            if "good" in url:
                return ExtractedDocument(
                    url=url,
                    title="Good",
                    text="Lithium costs more than silver per kilogram in 2024 markets.",
                    publisher="NIH",
                    authors=None,
                    publication_date=None,
                )
            return ExtractedDocument(
                url=url,
                title="Bad",
                text="Rhodium and iridium are the most expensive elements by mass.",
                publisher="NIH",
                authors=None,
                publication_date=None,
            )

    search = StaticUrlSearch(
        [
            "https://www.nih.gov/bad",
            "https://www.nih.gov/good",
        ]
    )
    hits = await discover_reputable_sources(
        "Lithium is more expensive than silver.",
        cfg=cfg,
        extractor=_Extractor(),
        search=search,
    )
    assert len(hits) == 1
    assert "good" in hits[0].url
    assert "lithium" in hits[0].excerpt.lower()

