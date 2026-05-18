"""Fetch and normalize external URL content for evidence (delegates to HtmlExtractor)."""

from __future__ import annotations

from app.services.evidence.html_extractor import HtmlExtractor


class UrlFetchService:
    """Backward-compatible wrapper around structured HTML extraction."""

    def __init__(self, *, timeout: float = 20.0) -> None:
        self._extractor = HtmlExtractor(timeout=timeout)

    async def fetch(self, url: str) -> dict[str, str | None]:
        """Return title, text, publisher guess, and error if any."""
        doc = await self._extractor.extract(url)
        return {
            "error": doc.error,
            "text": doc.text or None,
            "title": doc.title or url,
            "publisher": doc.publisher,
            "fetched_at": doc.retrieval_timestamp.isoformat(),
        }
