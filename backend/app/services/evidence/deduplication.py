"""Content-hash and URL normalization for evidence deduplication."""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Canonical URL form for dedupe keys (strip fragment, trailing slash)."""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def content_hash(*, url: str, text: str) -> str:
    """Stable SHA-256 over normalized URL and cleaned body."""
    normalized = normalize_url(url)
    payload = f"{normalized}\n{(text or '').strip()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
