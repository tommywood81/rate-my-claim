"""Pick short excerpts from fetched page text."""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9']+")


def _keywords(text: str) -> set[str]:
    words = {w for w in _WORD.findall(text.lower()) if len(w) > 2}
    stop = {
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
    }
    return words - stop


def pick_relevant_excerpt(text: str, claim_text: str, *, max_chars: int = 320) -> str:
    """Return one or two sentences most overlapping the claim (deterministic)."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""

    claim_keys = _keywords(claim_text)
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(cleaned) if s.strip()]
    if not sentences:
        return cleaned[:max_chars].rstrip() + ("…" if len(cleaned) > max_chars else "")
    if len(sentences) == 1 and len(sentences[0]) <= max_chars:
        return sentences[0]

    scored: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences[:40]):
        keys = _keywords(sentence)
        overlap = len(keys & claim_keys)
        length_penalty = len(sentence) / max(max_chars, 1)
        score = overlap * 2.0 - length_penalty * 0.15
        scored.append((score, idx, sentence))

    scored.sort(key=lambda row: (-row[0], row[1]))
    if not scored or scored[0][0] <= 0:
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
