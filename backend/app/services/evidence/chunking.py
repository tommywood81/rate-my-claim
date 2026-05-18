"""Split extracted text into overlapping chunks for embedding and retrieval."""

from __future__ import annotations


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[str]:
    """Return non-empty text chunks with paragraph-aware boundaries."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue
        if buffer:
            chunks.extend(_split_long(buffer, chunk_size=chunk_size, overlap=overlap))
        buffer = para
    if buffer:
        chunks.extend(_split_long(buffer, chunk_size=chunk_size, overlap=overlap))

    out: list[str] = []
    seen: set[str] = set()
    for c in chunks:
        piece = c.strip()
        if piece and piece not in seen:
            seen.add(piece)
            out.append(piece)
    return out


def _split_long(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Hard-split long paragraphs with overlap."""
    if len(text) <= chunk_size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return [p for p in parts if p]
