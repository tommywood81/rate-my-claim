"""Search query variants for reputable source discovery."""

from __future__ import annotations

import re

from app.services.enrichment.excerpt_utils import _keywords, substantive_claim_keywords

_COMPARATIVE = frozenset(
    {
        "expensive",
        "cheaper",
        "cheapest",
        "costlier",
        "price",
        "prices",
        "cost",
        "costs",
        "than",
        "versus",
        "vs",
    }
)


def build_discovery_queries(claim_text: str) -> list[str]:
    """
    Build several search strings so allowlisted domains appear in results.

    A single verbatim claim often surfaces only one Wikipedia hit; price/comparison
    claims benefit from keyword-focused follow-up queries.
    """
    base = " ".join(claim_text.split())[:180]
    if not base:
        return []

    keys = sorted(substantive_claim_keywords(claim_text), key=len, reverse=True)
    seen: set[str] = set()
    out: list[str] = []

    def _add(q: str) -> None:
        normalized = " ".join(q.split()).strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(" ".join(q.split()).strip())

    _add(base)
    if keys:
        _add(" ".join(keys[:8]))
    if len(keys) >= 2:
        _add(" ".join(keys[:4]))

    lower = base.lower()
    if _COMPARATIVE & set(lower.split()):
        substantive = [k for k in keys if k not in _COMPARATIVE]
        if len(substantive) >= 2:
            _add(" ".join(substantive[:4]) + " price comparison")
            _add(" ".join(substantive[:2]) + " price per gram")
        elif len(substantive) == 1:
            _add(substantive[0] + " price")

    # Entity-targeted allowlisted searches (capitalized words + substantive keywords)
    entity_tokens: list[str] = []
    for token in re.findall(r"\b[A-Z][a-z]{2,}\b", claim_text):
        entity_tokens.append(token)
    for word in keys:
        titled = word.title()
        if titled not in entity_tokens:
            entity_tokens.append(titled)
    for token in entity_tokens[:4]:
        _add(f"{token} site:britannica.com")
        _add(f"{token} site:wikipedia.org")
        if _COMPARATIVE & set(lower.split()):
            _add(f"{token} price site:wikipedia.org")

    return out[:10]
