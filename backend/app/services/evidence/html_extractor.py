"""HTML download, readability parsing, and metadata extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import trafilatura

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDocument:
    """Structured extraction result with provenance preserved."""

    url: str
    title: str
    text: str
    publisher: str | None
    authors: str | None
    publication_date: datetime | None
    citations: list[dict[str, str]] = field(default_factory=list)
    extraction_metadata: dict[str, Any] = field(default_factory=dict)
    retrieval_timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    retrieval_source: str = "html_fetch"
    error: str | None = None


class HtmlExtractor:
    """Fetch HTML and extract readable content via trafilatura."""

    def __init__(self, *, timeout: float = 20.0) -> None:
        self._timeout = timeout

    async def extract(self, url: str) -> ExtractedDocument:
        """Download and parse a single URL."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return ExtractedDocument(
                url=url,
                title=url,
                text="",
                publisher=None,
                authors=None,
                publication_date=None,
                error="unsupported_scheme",
            )
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": "RateMyClaimBot/1.0 (+https://rate-my-claim.local)"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                final_url = str(resp.url)
        except httpx.HTTPError as exc:
            logger.info("html_extract_http_error", extra={"url": url, "error": str(exc)})
            return ExtractedDocument(
                url=url,
                title=url,
                text="",
                publisher=parsed.netloc,
                authors=None,
                publication_date=None,
                error=str(exc),
            )

        extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
        meta = trafilatura.extract_metadata(html)
        title = (meta.title if meta and meta.title else url) or url
        publisher = meta.sitename if meta and meta.sitename else urlparse(final_url).netloc
        authors = meta.author if meta and meta.author else None
        pub_date = None
        if meta and meta.date:
            try:
                pub_date = datetime.fromisoformat(str(meta.date).replace("Z", "+00:00"))
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=UTC)
            except ValueError:
                pub_date = None

        from app.services.evidence.citations import extract_citations

        body = extracted or ""
        citations = extract_citations(body)
        metadata: dict[str, Any] = {
            "final_url": final_url,
            "hostname": urlparse(final_url).netloc,
            "language": meta.language if meta else None,
            "description": meta.description if meta else None,
            "tags": list(meta.tags) if meta and meta.tags else [],
        }

        return ExtractedDocument(
            url=final_url,
            title=title,
            text=body,
            publisher=publisher,
            authors=authors,
            publication_date=pub_date,
            citations=citations,
            extraction_metadata=metadata,
            retrieval_source="trafilatura",
        )
