"""Extract citation-like references from article text."""

from __future__ import annotations

import re

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s\]\)\"']+", re.IGNORECASE)


def extract_citations(text: str, *, max_items: int = 40) -> list[dict[str, str]]:
    """Return deduplicated DOI and URL citations found in body text."""
    if not text:
        return []
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in _DOI_RE.finditer(text):
        doi = match.group(0)
        key = f"doi:{doi.lower()}"
        if key in seen:
            continue
        seen.add(key)
        found.append({"kind": "doi", "value": doi})

    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;)")
        key = f"url:{url.lower()}"
        if key in seen:
            continue
        seen.add(key)
        found.append({"kind": "url", "value": url})

    return found[:max_items]
