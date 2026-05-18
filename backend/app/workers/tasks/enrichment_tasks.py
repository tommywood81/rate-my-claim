"""Async enrichment pipeline invoked from Celery."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
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
from app.services.retrieval.url_fetch_service import UrlFetchService

logger = logging.getLogger(__name__)

_TERMINAL = frozenset(
    {
        ProcessingStatus.awaiting_moderation,
        ProcessingStatus.completed,
        ProcessingStatus.rejected,
        ProcessingStatus.revision_requested,
    }
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
                vec, pending_id=pending.id
            )

            pending.processing_status = ProcessingStatus.canonicalizing
            await session.flush()
            await audit.log_stage(pending_id=pending_id, stage="canonicalizing")

            canon = await canon_svc.canonicalize(pending.raw_claim_text, provider)
            rejection = canon.get("rejection_reason")
            if rejection:
                pending.canonical_candidate_text = None
                pending.normalized_claim_text = normalize_claim_text(pending.raw_claim_text)
                await ai_repo.add_analysis(
                    target_type="pending_claim",
                    target_id=pending.id,
                    model_name=settings.ai_model_cheap,
                    provider=provider.name,
                    analysis_type="canonicalization_rejected",
                    generated_text=str(rejection),
                    structured_payload=canon,
                    created_by_job="enrichment",
                )
                pending.processing_status = ProcessingStatus.awaiting_moderation
                pending.ai_summary = "Claim requires moderator review (automatic rejection hint)."
                await audit.log_stage(
                    pending_id=pending_id,
                    stage="awaiting_moderation",
                    details={"canonicalization_rejected": True},
                )
                await session.commit()
                return

            pending.canonical_candidate_text = str(canon.get("canonical_text", "")).strip()
            pending.normalized_claim_text = str(canon.get("normalized_text", "")).strip()

            pending.processing_status = ProcessingStatus.enriching
            await session.flush()
            await audit.log_stage(pending_id=pending_id, stage="enriching")

            fetcher = UrlFetchService()
            url_blocks: list[dict[str, str]] = []
            urls = list(pending.source_urls or [])
            for url in urls[:12]:
                payload = await fetcher.fetch(str(url))
                if payload.get("text"):
                    url_blocks.append(
                        {
                            "url": str(url),
                            "title": str(payload.get("title") or url),
                            "text": str(payload.get("text"))[:4000],
                            "publisher": str(payload.get("publisher") or ""),
                        }
                    )

            canonical = pending.canonical_candidate_text or pending.raw_claim_text
            evidence_ctx = await repo.evidence_for_similar_claims(vec, limit=24)
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

            context = "\n".join(lines) if lines else "(no retrieved context)"
            verdict = await provider.structured_verdict(canonical, context)
            await ai_repo.add_analysis(
                target_type="pending_claim",
                target_id=pending.id,
                model_name=settings.ai_model_reasoning,
                provider=provider.name,
                analysis_type="structured_verdict",
                generated_text=str(verdict.get("verdict_summary", "")),
                structured_payload={"verdict": verdict, "line_map": line_map},
                confidence=float(verdict.get("confidence_hint", 0.5) or 0.5),
                created_by_job="enrichment",
            )

            digest = "\n".join(lines[:20])
            scores = await provider.generate_confidence_analysis(canonical, digest)
            await ai_repo.add_analysis(
                target_type="pending_claim",
                target_id=pending.id,
                model_name=settings.ai_model_reasoning,
                provider=provider.name,
                analysis_type="confidence_analysis",
                generated_text=str(scores.get("rationale", "")),
                structured_payload=scores,
                confidence=float(scores.get("aggregate", 0.5) or 0.5),
                created_by_job="enrichment",
            )

            summary = await provider.summarize_evidence(context[:8000])
            pending.ai_summary = summary
            pending.processing_status = ProcessingStatus.awaiting_moderation
            await audit.log_stage(
                pending_id=pending_id,
                stage="awaiting_moderation",
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
                    await session2.commit()
        except Exception as exc:
            logger.exception("enrichment_failed", extra={"pending_id": str(pending_id)})
            await session.rollback()
            async with AsyncSessionLocal() as session2:
                p2 = await session2.get(PendingClaim, pending_id)
                if p2:
                    p2.processing_status = ProcessingStatus.failed
                    p2.error_message = str(exc)[:4000]
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
