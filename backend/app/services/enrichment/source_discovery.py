"""Discover and fetch up to N reputable web sources for one enrichment run."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.enrichment_pipeline_config import SourceDiscoveryConfig
from app.services.enrichment.excerpt_utils import pick_relevant_excerpt
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


def _search_query(claim_text: str) -> str:
    text = " ".join(claim_text.split())
    return text[:180]


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

    Returns fewer than max_sources when search or fetch fails — never pads with junk.
    """
    if not cfg.enabled or cfg.max_sources <= 0:
        return []

    allowlist = load_allowlisted_publishers(cfg.allowlist_config_path)
    if not allowlist:
        logger.warning("reputable_allowlist_empty")
        return []

    query = _search_query(claim_text)
    search_impl = search or default_web_search(timeout=cfg.fetch_timeout_seconds)
    extractor_impl = extractor or HtmlExtractor(timeout=cfg.fetch_timeout_seconds)

    candidate_urls = await search_impl.search(query, limit=cfg.search_result_limit)
    ranked: list[tuple[float, str, AllowlistedPublisher]] = []
    seen_hosts: set[str] = set()
    for url in candidate_urls:
        match = match_allowlisted_publisher(url, allowlist)
        if match is None:
            continue
        if match.credibility < cfg.min_publisher_credibility:
            continue
        host_key = match.domain
        if host_key in seen_hosts:
            continue
        seen_hosts.add(host_key)
        ranked.append((match.credibility, url, match))

    ranked.sort(key=lambda row: -row[0])
    targets = ranked[: cfg.max_sources]
    if not targets:
        logger.info("reputable_source_no_allowlist_hits", extra={"query": query[:120]})
        return []

    async def _run(url: str, publisher: AllowlistedPublisher) -> ReputableSourceHit | None:
        return await _fetch_one(
            url,
            claim_text=claim_text,
            publisher=publisher,
            extractor=extractor_impl,
            excerpt_max_chars=cfg.excerpt_max_chars,
        )

    results = await asyncio.gather(
        *[_run(url, publisher) for _cred, url, publisher in targets],
        return_exceptions=True,
    )

    hits: list[ReputableSourceHit] = []
    for item in results:
        if isinstance(item, ReputableSourceHit):
            hits.append(item)
        elif isinstance(item, Exception):
            logger.info("reputable_source_fetch_error", extra={"error": str(item)})
    return hits
