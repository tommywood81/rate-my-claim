"""Discover and fetch up to N reputable web sources for one enrichment run."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.enrichment_pipeline_config import SourceDiscoveryConfig
from app.services.enrichment.discovery_queries import build_discovery_queries
from app.services.enrichment.excerpt_utils import (
    excerpt_claim_overlap,
    excerpt_meets_relevance,
    pick_relevant_excerpt,
)
from app.services.enrichment.reputable_allowlist import (
    AllowlistedPublisher,
    load_allowlisted_publishers,
    match_allowlisted_publisher,
)
from app.services.enrichment.web_search import WebSearchProvider, default_web_search
from app.services.evidence.html_extractor import ExtractedDocument, HtmlExtractor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReputableSourceHit:
    """One fetched allowlisted source ready for assessment context and finalize."""

    url: str
    title: str
    publisher: str
    excerpt: str
    credibility_score: float
    retrieved_at: datetime
    publication_date: datetime | None = None


def hits_to_url_blocks(hits: list[ReputableSourceHit]) -> list[dict[str, Any]]:
    """Map discovery hits to enrichment/finalize url blocks."""
    blocks: list[dict[str, Any]] = []
    for hit in hits:
        blocks.append(
            {
                "kind": "url",
                "url": hit.url,
                "title": hit.title,
                "publisher": hit.publisher,
                "text": hit.excerpt,
                "credibility_score": hit.credibility_score,
                "retrieved_at": hit.retrieved_at.isoformat(),
                "publication_date": hit.publication_date.isoformat() if hit.publication_date else None,
                "source_channel": "reputable_web",
            }
        )
    return blocks


async def _collect_candidate_urls(
    claim_text: str,
    *,
    search: WebSearchProvider,
    search_result_limit: int,
) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for query in build_discovery_queries(claim_text):
        batch = await search.search(query, limit=search_result_limit)
        for url in batch:
            if url in seen:
                continue
            seen.add(url)
            ordered.append(url)
    return ordered


def _rank_allowlisted_candidates(
    candidate_urls: list[str],
    allowlist: list,
    *,
    cfg: SourceDiscoveryConfig,
) -> list[tuple[float, str, AllowlistedPublisher]]:
    ranked: list[tuple[float, str, AllowlistedPublisher]] = []
    domain_counts: dict[str, int] = {}
    for url in candidate_urls:
        match = match_allowlisted_publisher(url, allowlist)
        if match is None:
            continue
        if match.credibility < cfg.min_publisher_credibility:
            continue
        host_key = match.domain
        count = domain_counts.get(host_key, 0)
        if count >= cfg.max_urls_per_domain:
            continue
        domain_counts[host_key] = count + 1
        ranked.append((match.credibility, url, match))

    ranked.sort(key=lambda row: (-row[0], row[1]))
    return ranked


async def _fetch_one(
    url: str,
    *,
    claim_text: str,
    publisher: AllowlistedPublisher,
    extractor: HtmlExtractor,
    excerpt_max_chars: int,
) -> ReputableSourceHit | None:
    doc: ExtractedDocument = await extractor.extract(url)
    if doc.error or not doc.text.strip():
        logger.info(
            "reputable_source_fetch_empty",
            extra={"url": url, "error": doc.error or "empty_text"},
        )
        return None
    excerpt = pick_relevant_excerpt(doc.text, claim_text, max_chars=excerpt_max_chars)
    if not excerpt:
        return None
    retrieved = doc.retrieval_timestamp or datetime.now(tz=UTC)
    return ReputableSourceHit(
        url=doc.url or url,
        title=(doc.title or url)[:512],
        publisher=publisher.publisher,
        excerpt=excerpt,
        credibility_score=publisher.credibility,
        retrieved_at=retrieved,
        publication_date=doc.publication_date,
    )


async def discover_reputable_sources(
    claim_text: str,
    *,
    cfg: SourceDiscoveryConfig,
    extractor: HtmlExtractor | None = None,
    search: WebSearchProvider | None = None,
) -> list[ReputableSourceHit]:
    """
    Search the web, keep allowlisted hosts, fetch pages, and return up to max_sources hits.

    Tries multiple query variants and skips excerpts that do not mention claim keywords.
    """
    if not cfg.enabled or cfg.max_sources <= 0:
        return []

    allowlist = load_allowlisted_publishers(cfg.allowlist_config_path)
    if not allowlist:
        logger.warning("reputable_allowlist_empty")
        return []

    search_impl = search or default_web_search(timeout=cfg.fetch_timeout_seconds)
    extractor_impl = extractor or HtmlExtractor(timeout=cfg.fetch_timeout_seconds)

    candidate_urls = await _collect_candidate_urls(
        claim_text,
        search=search_impl,
        search_result_limit=cfg.search_result_limit,
    )
    ranked = _rank_allowlisted_candidates(candidate_urls, allowlist, cfg=cfg)
    if not ranked:
        logger.info(
            "reputable_source_no_allowlist_hits",
            extra={"query": claim_text[:120], "candidates": len(candidate_urls)},
        )
        return []

    fetch_targets = ranked[: cfg.max_candidate_fetches]

    async def _run(url: str, publisher: AllowlistedPublisher) -> ReputableSourceHit | None:
        return await _fetch_one(
            url,
            claim_text=claim_text,
            publisher=publisher,
            extractor=extractor_impl,
            excerpt_max_chars=cfg.excerpt_max_chars,
        )

    results = await asyncio.gather(
        *[_run(url, publisher) for _cred, url, publisher in fetch_targets],
        return_exceptions=True,
    )

    min_overlap = cfg.min_excerpt_keyword_overlap
    scored_hits: list[tuple[int, float, ReputableSourceHit]] = []
    for item in results:
        if isinstance(item, Exception):
            logger.info("reputable_source_fetch_error", extra={"error": str(item)})
            continue
        if not isinstance(item, ReputableSourceHit):
            continue
        if not excerpt_meets_relevance(
            item.excerpt, claim_text, min_overlap=min_overlap
        ):
            overlap = excerpt_claim_overlap(item.excerpt, claim_text)
            logger.info(
                "reputable_source_excerpt_irrelevant",
                extra={"url": item.url, "overlap": overlap, "min": min_overlap},
            )
            continue
        overlap = excerpt_claim_overlap(item.excerpt, claim_text)
        scored_hits.append((overlap, item.credibility_score, item))

    scored_hits.sort(key=lambda row: (-row[0], -row[1]))
    hits = [item for _ov, _cred, item in scored_hits[: cfg.max_sources]]

    if len(hits) < cfg.max_sources:
        logger.info(
            "reputable_source_partial",
            extra={
                "wanted": cfg.max_sources,
                "saved": len(hits),
                "fetched": len(fetch_targets),
                "allowlisted": len(ranked),
            },
        )
    return hits
