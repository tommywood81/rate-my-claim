"""Web search helpers for reputable source discovery."""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Protocol
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

_DDG_UDDG = re.compile(r"uddg=([^&\"]+)")
_DDG_RESULT_LINK = re.compile(r'class="result__a"[^>]*href="([^"]+)"', re.IGNORECASE)

# DuckDuckGo returns 202 with no results for obvious bot User-Agents.
_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; RateMyClaim/1.0; +https://rate-my-claim.local; enrichment)"
)
_WIKI_UA = "RateMyClaim/1.0 (https://rate-my-claim.local; enrichment source discovery)"

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "he",
        "her",
        "his",
        "in",
        "is",
        "it",
        "its",
        "not",
        "of",
        "on",
        "or",
        "she",
        "that",
        "the",
        "their",
        "they",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
    }
)


class WebSearchProvider(Protocol):
    """Return candidate result URLs for a query."""

    async def search(self, query: str, *, limit: int) -> list[str]: ...


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in urls:
        if not raw.startswith(("http://", "https://")):
            continue
        host = (urlparse(raw).hostname or "").lower()
        if not host or "duckduckgo.com" in host:
            continue
        if raw in seen:
            continue
        seen.add(raw)
        out.append(raw)
    return out


def _parse_ddg_html(html: str, *, limit: int) -> list[str]:
    urls: list[str] = []
    for match in _DDG_UDDG.finditer(html):
        urls.append(unescape(unquote(match.group(1))))
    for match in _DDG_RESULT_LINK.finditer(html):
        urls.append(unescape(match.group(1)))
    return _dedupe_urls(urls)[:limit]


def wikipedia_query_variants(query: str) -> list[str]:
    """Build progressively shorter queries for Wikipedia OpenSearch."""
    text = " ".join(query.split())
    if not text:
        return []

    words = [w for w in text.split() if w.lower() not in _STOP_WORDS]
    variants: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        key = candidate.strip().lower()
        if key and key not in seen:
            seen.add(key)
            variants.append(candidate.strip())

    _add(text)
    if words:
        _add(" ".join(words[:8]))
        for size in (6, 4, 3, 2):
            if len(words) >= size:
                _add(" ".join(words[:size]))
    return variants


class DuckDuckGoHtmlSearch:
    """HTML scrape search (no API key). Results are filtered downstream by allowlist."""

    def __init__(self, *, timeout: float = 12.0, user_agent: str = _DEFAULT_UA) -> None:
        self._timeout = timeout
        self._user_agent = user_agent

    async def search(self, query: str, *, limit: int) -> list[str]:
        if not query.strip():
            return []
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            ) as client:
                resp = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query, "b": ""},
                )
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPError as exc:
            logger.info("web_search_failed", extra={"query": query[:120], "error": str(exc)})
            return []

        urls = _parse_ddg_html(html, limit=limit)
        if not urls:
            logger.info(
                "web_search_no_results",
                extra={"query": query[:120], "provider": "duckduckgo"},
            )
        return urls


class WikipediaOpenSearch:
    """Wikipedia API fallback — reliable when DDG blocks or returns nothing."""

    def __init__(self, *, timeout: float = 12.0) -> None:
        self._timeout = timeout

    async def search(self, query: str, *, limit: int) -> list[str]:
        if not query.strip() or limit <= 0:
            return []

        urls: list[str] = []
        seen: set[str] = set()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": _WIKI_UA},
                follow_redirects=True,
            ) as client:
                for variant in wikipedia_query_variants(query):
                    if len(urls) >= limit:
                        break
                    resp = await client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={
                            "action": "opensearch",
                            "search": variant,
                            "limit": min(limit, 5),
                            "format": "json",
                        },
                    )
                    if resp.status_code != 200:
                        continue
                    payload = resp.json()
                    if not isinstance(payload, list) or len(payload) < 4:
                        continue
                    for url in payload[3]:
                        if not isinstance(url, str) or not url.startswith("https://"):
                            continue
                        if url in seen:
                            continue
                        seen.add(url)
                        urls.append(url)
                        if len(urls) >= limit:
                            break
        except (httpx.HTTPError, ValueError) as exc:
            logger.info(
                "web_search_failed",
                extra={"query": query[:120], "provider": "wikipedia", "error": str(exc)},
            )
            return urls

        if not urls:
            logger.info(
                "web_search_no_results",
                extra={"query": query[:120], "provider": "wikipedia"},
            )
        return urls[:limit]


class CompositeWebSearch:
    """Try multiple providers until enough candidate URLs are found."""

    def __init__(self, providers: list[WebSearchProvider]) -> None:
        self._providers = providers

    async def search(self, query: str, *, limit: int) -> list[str]:
        if limit <= 0:
            return []
        merged: list[str] = []
        seen: set[str] = set()
        for provider in self._providers:
            batch = await provider.search(query, limit=limit)
            for url in batch:
                if url in seen:
                    continue
                seen.add(url)
                merged.append(url)
                if len(merged) >= limit:
                    return merged
        return merged


def default_web_search(*, timeout: float = 12.0) -> WebSearchProvider:
    """Primary search stack used during enrichment."""
    return CompositeWebSearch(
        [
            DuckDuckGoHtmlSearch(timeout=timeout),
            WikipediaOpenSearch(timeout=timeout),
        ]
    )


class StaticUrlSearch:
    """Test helper: return a fixed URL list regardless of query."""

    def __init__(self, urls: list[str]) -> None:
        self._urls = list(urls)

    async def search(self, query: str, *, limit: int) -> list[str]:
        _ = query
        return self._urls[:limit]
