"""Build numbered evidence context for enrichment prompts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.enrichment_pipeline_config import RetrievalStageConfig
from app.models.evidence import Evidence
from app.services.evidence.ingestion_service import EvidenceIngestionService


@dataclass(frozen=True)
class EvidenceContextBundle:
    """Numbered lines for model prompts plus finalize line_map."""

    lines: list[str]
    line_map: dict[int, dict[str, Any]]
    has_corpus_evidence: bool
    context: str
    digest: str


def build_evidence_context(
    *,
    evidence_rows: list[Evidence],
    url_blocks: list[dict[str, str]],
    retrieval: RetrievalStageConfig,
    empty_digest_prompt: str,
) -> EvidenceContextBundle:
    """Assemble capped context lines from DB evidence and URL artifacts."""
    line_map: dict[int, dict[str, Any]] = {}
    lines: list[str] = []
    idx = 1
    excerpt_cap = retrieval.excerpt_max_chars

    for ev in evidence_rows[: retrieval.evidence_line_limit]:
        excerpt = (ev.summary or ev.cleaned_content or "")[:excerpt_cap]
        block = f"[claim-evidence id={ev.id}] {ev.title}: {excerpt}"
        lines.append(f"{idx}. {block}")
        line_map[idx] = {
            "kind": "db_evidence",
            "evidence_id": str(ev.id),
            "title": ev.title,
            "excerpt": excerpt,
        }
        idx += 1
        if len(lines) >= retrieval.evidence_line_limit:
            break

    for block in url_blocks:
        if len(lines) >= retrieval.evidence_line_limit:
            break
        text = (block.get("text") or "")[:excerpt_cap]
        title = block.get("title") or block.get("url") or "Source"
        lines.append(f"{idx}. [url] {title} — {text}")
        line_map[idx] = {"kind": "url", **block, "text": text}
        idx += 1

    has_corpus = bool(lines)
    context = "\n".join(lines) if lines else "(no corpus evidence retrieved)"
    if len(context) > retrieval.context_max_chars:
        context = context[: retrieval.context_max_chars]

    digest_lines = lines[: retrieval.digest_line_limit]
    digest = "\n".join(digest_lines) if digest_lines else empty_digest_prompt
    if len(digest) > retrieval.context_max_chars:
        digest = digest[: retrieval.context_max_chars]

    return EvidenceContextBundle(
        lines=lines,
        line_map=line_map,
        has_corpus_evidence=has_corpus,
        context=context,
        digest=digest,
    )


def url_blocks_from_artifacts(
    artifacts: list,
    *,
    excerpt_chars: int,
) -> list[dict[str, str]]:
    """Map artifacts to enrichment blocks with excerpt cap."""
    blocks: list[dict[str, str]] = []
    for artifact in artifacts:
        if not getattr(artifact, "cleaned_content", None):
            continue
        block = EvidenceIngestionService.artifact_to_context_block(artifact)
        block["text"] = (block.get("text") or "")[:excerpt_chars]
        blocks.append(block)
    return blocks
