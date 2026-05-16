"""Deterministic claim text normalization before AI canonicalization."""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def normalize_claim_text(raw: str) -> str:
    """Collapse whitespace, strip, and normalize common punctuation for dedupe keys."""
    text = raw.strip()
    text = _WHITESPACE.sub(" ", text)
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text
