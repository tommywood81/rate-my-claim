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
from app.services.retrieval.url_fetch_service import UrlFetchService

logger = logging.getLogger(__name__)


async def _run_pipeline(pending_id: UUID) -> None:
    """Execute embedding, dedupe, canonicalization, retrieval, and verdict."""
    settings = get_settings()
    provider = get_ai_provider()
    async with AsyncSessionLocal() as session:
        repo = ClaimRepository(session)
        ai_repo = AIAnalysisRepository(session)
        pending = await repo.get_pending(pending_id)
        if pending is None:
            return
        if pending.processing_status in {
            ProcessingStatus.awaiting_moderation,
            ProcessingStatus.completed,
            ProcessingStatus.rejected,
        }:
            return

        try:
            pending.processing_status = ProcessingStatus.embedding
            await session.flush()

            vec, emb_model = await provider.generate_embedding(pending.raw_claim_text)
            pending.embedding = vec
            pending.embedding_model = emb_model
            pending.embedding_version = settings.embedding_version
            pending.embedding_at = datetime.now(tz=UTC)
            pending.processing_status = ProcessingStatus.duplicate_check
            await session.flush()

            dup_ids: list[str] = []
            for claim, dist in await repo.vector_similar_claims(vec, limit=12, exclude_id=None):
                sim = 1.0 - float(dist)
                if sim >= settings.duplicate_vector_threshold:
                    dup_ids.append(str(claim.id))
            for other, dist in await repo.vector_similar_pending(vec, limit=8, exclude_id=pending.id):
                sim = 1.0 - float(dist)
                if sim >= settings.duplicate_vector_threshold:
                    dup_ids.append(f"pending:{other.id}")
            pending.duplicate_candidate_ids = dup_ids[:50]

            pending.processing_status = ProcessingStatus.canonicalizing
            await session.flush()

            canon = await provider.canonicalize_claim(pending.raw_claim_text)
            rejection = canon.get("rejection_reason")
            if rejection:
                pending.canonical_candidate_text = None
                pending.normalized_claim_text = pending.raw_claim_text.strip()
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
                await session.commit()
                return

            canonical = str(canon.get("canonical_text") or pending.raw_claim_text).strip()
            normalized = str(canon.get("normalized_text") or canonical).strip()
            pending.canonical_candidate_text = canonical
            pending.normalized_claim_text = normalized

            pending.processing_status = ProcessingStatus.enriching
            await session.flush()

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

            evidence_ctx = await repo.evidence_for_similar_claims(vec, limit=24)
            line_map: dict[int, dict[str, str]] = {}
            lines: list[str] = []
            idx = 1
            for ev in evidence_ctx:
                block = f"[claim-evidence id={ev.id}] {ev.title}: {(ev.summary or ev.cleaned_content or '')[:900]}"
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
            await session.commit()
        except Exception as exc:
            logger.exception("enrichment_failed", extra={"pending_id": str(pending_id)})
            await session.rollback()
            async with AsyncSessionLocal() as session2:
                p2 = await session2.get(PendingClaim, pending_id)
                if p2:
                    p2.processing_status = ProcessingStatus.failed
                    p2.error_message = str(exc)[:4000]
                    await session2.commit()


def run_pending_enrichment(pending_id: str) -> None:
    """Sync entrypoint for Celery worker."""
    asyncio.run(_run_pipeline(UUID(pending_id)))
