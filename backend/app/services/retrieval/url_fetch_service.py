"""Fetch and normalize external URL content for evidence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
import trafilatura

logger = logging.getLogger(__name__)


class UrlFetchService:
    """Download HTML and extract readable text with provenance."""

    def __init__(self, *, timeout: float = 20.0) -> None:
        """Configure HTTP client timeout."""
        self._timeout = timeout

    async def fetch(self, url: str) -> dict[str, str | None]:
        """Return title, text, publisher guess, and error if any."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return {"error": "unsupported_scheme", "text": None, "title": None, "publisher": None}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": "RateMyClaimBot/1.0 (+https://rate-my-claim.local)"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPError as exc:
            logger.info("url_fetch_http_error", extra={"url": url, "error": str(exc)})
            return {"error": str(exc), "text": None, "title": None, "publisher": parsed.netloc}

        extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
        meta = trafilatura.extract_metadata(html)
        title = meta.title if meta else None
        return {
            "error": None,
            "text": extracted or "",
            "title": title or url,
            "publisher": meta.sitename if meta and meta.sitename else parsed.netloc,
            "fetched_at": datetime.now(tz=UTC).isoformat(),
        }
