"""Async enrichment pipeline invoked from Celery."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.claim import PendingClaim, ProcessingStatus
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.claims_repository import ClaimRepository
from app.services.ai.factory import get_ai_provider
from app.services.ai.idempotency import enrichment_task_lock
from app.services.ai.token_budget import TokenBudgetExceeded
from app.services.ingestion.canonicalization_service import CanonicalizationService
from app.services.ingestion.claim_normalization import normalize_claim_text
from app.services.ingestion.duplicate_detection_service import DuplicateDetectionService
from app.services.ingestion.pipeline_audit import IngestionPipelineAudit
from app.services.claims.assessment_finalize import finalize_pending_assessment
from app.services.claims.assessment_provenance import build_enrichment_provenance
from app.services.claims.live_claim_sync import sync_pending_to_linked_claim
from app.services.evidence.ingestion_service import EvidenceIngestionService

logger = logging.getLogger(__name__)

_TERMINAL = frozenset(
    {
        ProcessingStatus.awaiting_moderation,
        ProcessingStatus.completed,
        ProcessingStatus.rejected,
        ProcessingStatus.revision_requested,
    }
)

# Shown to the model when vector retrieval returns no archived evidence lines.
_EMPTY_DIGEST_PROMPT = (
    "ARCHIVE EVIDENCE: no matching sources were retrieved from this database.\n"
    "Assess the claim using well-established public knowledge (markets, science, units, etc.). "
    "Do not invent URLs or studies. Set evidence_quality between 0.1 and 0.35 to reflect "
    "the empty archive, but still choose a definite truth_label when the facts are widely known."
)


def _provisional_verdict_from_scores(scores: dict[str, Any]) -> dict[str, Any]:
    """Structured verdict when no corpus evidence lines were retrieved."""
    aggregate = float(scores.get("aggregate", 0.5) or 0.5)
    rationale = str(scores.get("rationale", "")).strip()
    truth = str(scores.get("truth_label", "")).strip().lower()
    controversy = float(scores.get("controversy_hint", 0.0) or 0.0)

    if rationale and truth in {"supported", "refuted"}:
        summary = rationale
    else:
        summary = (
            f"Assessment (confidence {aggregate:.0%}): no archived sources matched, "
            "but general knowledge may still apply. See the research summary."
        )

    return {
        "verdict_summary": summary,
        "citations": [],
        "confidence_hint": aggregate,
        "controversy_hint": controversy,
    }


def _research_summary_from_scores(
    scores: dict[str, Any],
    *,
    has_corpus_evidence: bool,
) -> str:
    """Public research summary: evidence-grounded digest, else confidence rationale."""
    if has_corpus_evidence:
        return ""
    rationale = str(scores.get("rationale", "")).strip()
    if rationale:
        return rationale
    return (
        "No matching evidence was found in the archive. "
        "A moderator can attach sources or re-run enrichment after more claims are indexed."
    )


async def _run_pipeline(pending_id: UUID) -> None:
    """Execute embedding, dedupe, canonicalization, retrieval, and verdict."""
    settings = get_settings()
    provider = get_ai_provider(budget_scope=f"pending:{pending_id}")
    canon_svc = CanonicalizationService()

    async with AsyncSessionLocal() as session:
        repo = ClaimRepository(session)
        ai_repo = AIAnalysisRepository(session)
        audit = IngestionPipelineAudit(session)
        pending = await repo.get_pending(pending_id)
        if pending is None:
            return
        if ProcessingStatus(str(pending.processing_status)) in _TERMINAL:
            return

        try:
            pending.normalized_claim_text = normalize_claim_text(pending.raw_claim_text)
            pending.processing_status = ProcessingStatus.embedding
            await session.flush()
            await sync_pending_to_linked_claim(session, pending_id)
            await audit.log_stage(pending_id=pending_id, stage="embedding")

            vec, emb_model = await provider.generate_embedding(pending.raw_claim_text)
            pending.embedding = vec
            pending.embedding_model = emb_model
            pending.embedding_version = settings.embedding_version
            pending.embedding_at = datetime.now(tz=UTC)
            pending.processing_status = ProcessingStatus.duplicate_check
            await session.flush()
            await audit.log_stage(
                pending_id=pending_id,
                stage="duplicate_check",
                details={"embedding_model": emb_model},
            )

            dup_svc = DuplicateDetectionService(session, settings)
            pending.duplicate_candidate_ids = await dup_svc.find_duplicate_candidate_ids(
                vec,
                pending_id=pending.id,
                exclude_claim_id=pending.linked_claim_id,
            )

            pending.processing_status = ProcessingStatus.canonicalizing
            await session.flush()
            await audit.log_stage(pending_id=pending_id, stage="canonicalizing")

            canon = await canon_svc.canonicalize(pending.raw_claim_text, provider)
            rejection = canon.get("rejection_reason")
            if rejection:
                await ai_repo.add_analysis(
                    target_type="pending_claim",
                    target_id=pending.id,
                    model_name=settings.ai_model_cheap,
                    provider=provider.name,
                    analysis_type="canonicalization_note",
                    generated_text=str(rejection),
                    structured_payload=canon,
                    created_by_job="enrichment",
                )

            canonical_text = str(canon.get("canonical_text", "")).strip()
            if not canonical_text:
                canonical_text = pending.raw_claim_text.strip()
            pending.canonical_candidate_text = canonical_text
            pending.normalized_claim_text = (
                str(canon.get("normalized_text", "")).strip()
                or normalize_claim_text(canonical_text)
            )
            await sync_pending_to_linked_claim(session, pending_id)

            pending.processing_status = ProcessingStatus.enriching
            await session.flush()
            await audit.log_stage(pending_id=pending_id, stage="enriching")

            ingestion_svc = EvidenceIngestionService(session)
            artifacts = await ingestion_svc.process_pending_jobs(
                pending_id,
                provider=provider,
                budget_scope=f"pending:{pending_id}",
            )
            url_blocks: list[dict[str, str]] = []
            for artifact in artifacts:
                if artifact.cleaned_content:
                    url_blocks.append(ingestion_svc.artifact_to_context_block(artifact))

            canonical = pending.canonical_candidate_text or pending.raw_claim_text
            evidence_ctx = await repo.evidence_for_similar_claims(
                vec,
                limit=24,
                min_similarity=settings.enrichment_retrieval_min_similarity,
                exclude_claim_id=pending.linked_claim_id,
            )
            line_map: dict[int, dict[str, str]] = {}
            lines: list[str] = []
            idx = 1
            for ev in evidence_ctx:
                excerpt = (ev.summary or ev.cleaned_content or "")[:900]
                block = f"[claim-evidence id={ev.id}] {ev.title}: {excerpt}"
                lines.append(f"{idx}. {block}")
                line_map[idx] = {
                    "kind": "db_evidence",
                    "evidence_id": str(ev.id),
                    "title": ev.title,
                    "excerpt": (ev.summary or ev.cleaned_content or "")[:900],
                }
                idx += 1
            for block in url_blocks:
                lines.append(f"{idx}. [url] {block['title']} — {block['text'][:900]}")
                line_map[idx] = {"kind": "url", **block}
                idx += 1

            has_corpus_evidence = bool(lines)
            context = "\n".join(lines) if lines else "(no corpus evidence retrieved)"
            digest = "\n".join(lines[:20]) if lines else _EMPTY_DIGEST_PROMPT
            run_at = datetime.now(tz=UTC)
            provenance = build_enrichment_provenance(
                pending=pending,
                canonical_claim_text=canonical,
                line_map=line_map,
                embedding_model=emb_model,
                embedding_version=settings.embedding_version,
                has_corpus_evidence=has_corpus_evidence,
                url_artifact_ids=[
                    str(b.get("artifact_id"))
                    for b in url_blocks
                    if b.get("artifact_id")
                ],
                borrowed_evidence_ids=[
                    str(line_map[k].get("evidence_id"))
                    for k in sorted(line_map)
                    if line_map[k].get("kind") == "db_evidence" and line_map[k].get("evidence_id")
                ],
                assessment_run_at=run_at,
            )

            scores = await provider.generate_confidence_analysis(canonical, digest)
            await ai_repo.add_analysis(
                target_type="pending_claim",
                target_id=pending.id,
                model_name=settings.ai_model_reasoning,
                provider=provider.name,
                analysis_type="confidence_analysis",
                generated_text=str(scores.get("rationale", "")),
                structured_payload={"scores": scores, "provenance": provenance},
                confidence=float(scores.get("aggregate", 0.5) or 0.5),
                created_by_job="enrichment",
            )

            if has_corpus_evidence:
                verdict = await provider.structured_verdict(canonical, context)
            else:
                verdict = _provisional_verdict_from_scores(scores)
            await ai_repo.add_analysis(
                target_type="pending_claim",
                target_id=pending.id,
                model_name=settings.ai_model_reasoning,
                provider=provider.name,
                analysis_type="structured_verdict",
                generated_text=str(verdict.get("verdict_summary", "")),
                structured_payload={
                    "verdict": verdict,
                    "line_map": line_map,
                    "provenance": provenance,
                },
                confidence=float(verdict.get("confidence_hint", 0.5) or 0.5),
                created_by_job="enrichment",
            )

            if has_corpus_evidence:
                summary_input = (
                    f"CLAIM UNDER REVIEW:\n{canonical}\n\n"
                    f"NUMBERED EVIDENCE LINES (summarize only lines that bear on this claim; "
                    f"if none apply, say no relevant evidence was found):\n{context[:7500]}"
                )
                summary = await provider.summarize_evidence(summary_input)
            else:
                summary = _research_summary_from_scores(scores, has_corpus_evidence=False)
            pending.ai_summary = summary
            await finalize_pending_assessment(
                session,
                pending_id,
                created_by_job="enrichment",
                explanation="Automated assessment published after enrichment.",
            )
            await audit.log_stage(
                pending_id=pending_id,
                stage="assessment_complete",
                details={
                    "duplicate_count": len(pending.duplicate_candidate_ids or []),
                    "url_blocks": len(url_blocks),
                },
            )
            await session.commit()
        except TokenBudgetExceeded as exc:
            logger.warning(
                "enrichment_token_budget",
                extra={"pending_id": str(pending_id), "detail": str(exc)},
            )
            await session.rollback()
            async with AsyncSessionLocal() as session2:
                p2 = await session2.get(PendingClaim, pending_id)
                if p2:
                    p2.processing_status = ProcessingStatus.failed
                    p2.error_message = f"OpenAI token budget exceeded: {exc}"
                    await sync_pending_to_linked_claim(session2, pending_id)
                    await session2.commit()
        except Exception as exc:
            logger.exception("enrichment_failed", extra={"pending_id": str(pending_id)})
            await session.rollback()
            async with AsyncSessionLocal() as session2:
                p2 = await session2.get(PendingClaim, pending_id)
                if p2:
                    p2.processing_status = ProcessingStatus.failed
                    p2.error_message = str(exc)[:4000]
                    await sync_pending_to_linked_claim(session2, pending_id)
                    await session2.commit()


async def enrich_pending_claim_async(pending_id: UUID | str) -> None:
    """Async entrypoint for tests and in-process callers."""
    pid = UUID(str(pending_id))
    async with enrichment_task_lock(pid) as acquired:
        if not acquired:
            return
        await _run_pipeline(pid)


def run_pending_enrichment(pending_id: str) -> None:
    """Sync entrypoint for Celery worker."""
    asyncio.run(enrich_pending_claim_async(pending_id))
