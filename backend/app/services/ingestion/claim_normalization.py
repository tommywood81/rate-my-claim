"""Deterministic claim text normalization before AI canonicalization."""

from __future__ import annotations

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")


def normalize_claim_text(raw: str) -> str:
    """Collapse whitespace, strip, and normalize common punctuation for dedupe keys."""
    text = raw.strip()
    text = _WHITESPACE.sub(" ", text)
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text


def claim_submission_fingerprint(normalized: str) -> str:
    """Stable SHA-256 hex digest for exact duplicate checks (case-insensitive)."""
    return hashlib.sha256(normalized.casefold().encode("utf-8")).hexdigest()


def normalized_texts_equivalent(a: str, b: str) -> bool:
    """True when two normalized strings differ only by case."""
    return a.casefold() == b.casefold()
