"""Pick short excerpts from fetched page text."""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9']+")

_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "with",
        "this",
        "from",
        "are",
        "was",
        "were",
        "has",
        "have",
        "not",
        "but",
        "can",
        "may",
        "will",
        "into",
        "about",
        "than",
        "when",
        "what",
        "which",
        "their",
        "they",
        "them",
        "also",
        "such",
        "been",
        "being",
        "does",
        "did",
        "its",
        "our",
        "your",
        "more",
        "less",
        "very",
    }
)


def _keywords(text: str) -> set[str]:
    words = {w for w in _WORD.findall(text.lower()) if len(w) > 2}
    return words - _STOP


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
        "more",
        "most",
        "less",
    }
)


def substantive_claim_keywords(claim_text: str) -> set[str]:
    """Claim keywords for relevance checks (drop vague comparatives)."""
    keys = _keywords(claim_text)
    substantive = {k for k in keys if k not in _COMPARATIVE}
    return substantive if substantive else keys


def excerpt_claim_overlap(excerpt: str, claim_text: str) -> int:
    """Count substantive claim keywords present in excerpt."""
    if not excerpt.strip():
        return 0
    return len(_keywords(excerpt) & substantive_claim_keywords(claim_text))


def excerpt_meets_relevance(
    excerpt: str,
    claim_text: str,
    *,
    min_overlap: int,
) -> bool:
    """True when excerpt mentions enough substantive terms from the claim."""
    if min_overlap <= 0:
        return bool(excerpt.strip())
    return excerpt_claim_overlap(excerpt, claim_text) >= min_overlap


def pick_keyword_window_excerpt(text: str, claim_text: str, *, max_chars: int) -> str:
    """Extract a window around the first strong claim keyword in raw page text."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""

    keys = sorted(_keywords(claim_text), key=len, reverse=True)
    lower = cleaned.lower()
    anchor = -1
    for key in keys:
        pos = lower.find(key)
        if pos >= 0:
            anchor = pos
            break
    if anchor < 0:
        return ""

    start = max(0, anchor - max_chars // 3)
    end = min(len(cleaned), start + max_chars)
    if end - start < max_chars and end < len(cleaned):
        start = max(0, end - max_chars)
    snippet = cleaned[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(cleaned):
        snippet = snippet.rstrip() + "…"
    return snippet


def pick_relevant_excerpt(text: str, claim_text: str, *, max_chars: int = 320) -> str:
    """Return one or two sentences most overlapping the claim (deterministic)."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""

    claim_keys = substantive_claim_keywords(claim_text)
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(cleaned) if s.strip()]
    if not sentences:
        return cleaned[:max_chars].rstrip() + ("…" if len(cleaned) > max_chars else "")
    if len(sentences) == 1 and len(sentences[0]) <= max_chars:
        return sentences[0]

    scored: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences[:60]):
        keys = _keywords(sentence)
        overlap = len(keys & claim_keys)
        length_penalty = len(sentence) / max(max_chars, 1)
        score = overlap * 2.0 - length_penalty * 0.15
        scored.append((score, idx, sentence))

    scored.sort(key=lambda row: (-row[0], row[1]))
    if not scored or scored[0][0] <= 0:
        window = pick_keyword_window_excerpt(cleaned, claim_text, max_chars=max_chars)
        if window and excerpt_claim_overlap(window, claim_text) > 0:
            return window
        best = scored[0][2] if scored else sentences[0]
        if len(best) > max_chars:
            return best[: max_chars - 1].rstrip() + "…"
        return best

    chosen: list[str] = []
    total = 0
    for score, _idx, sentence in scored:
        if score <= 0:
            break
        if not sentence:
            continue
        extra = len(sentence) + (2 if chosen else 0)
        if total + extra > max_chars and chosen:
            break
        chosen.append(sentence)
        total += extra
        if len(chosen) >= 2:
            break

    if not chosen:
        chosen = [sentences[0]]

    excerpt = " ".join(chosen)
    if len(excerpt) > max_chars:
        excerpt = excerpt[: max_chars - 1].rstrip() + "…"
    return excerpt
