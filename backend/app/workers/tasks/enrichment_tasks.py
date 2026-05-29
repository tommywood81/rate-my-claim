"""Async enrichment pipeline invoked from Celery."""

from __future__ import annotations

import asyncio

import logging

from datetime import UTC, datetime

from typing import Any

from uuid import UUID

from app.core.config import get_settings

from app.core.enrichment_pipeline_config import get_enrichment_pipeline_config

from app.db.session import AsyncSessionLocal

from app.models.claim import PendingClaim, ProcessingStatus

from app.repositories.ai_analysis_repository import AIAnalysisRepository

from app.repositories.claims_repository import ClaimRepository

from app.services.ai.factory import get_ai_provider

from app.services.ai.idempotency import enrichment_task_lock

from app.services.ai.token_budget import TokenBudgetExceeded

from app.services.claims.assessment_finalize import finalize_pending_assessment

from app.services.claims.assessment_provenance import build_enrichment_provenance

from app.services.claims.live_claim_sync import sync_pending_to_linked_claim

from app.services.enrichment.assessment_runner import resolve_research_summary, run_assessment_stage

from app.services.enrichment.context_builder import build_evidence_context, url_blocks_from_artifacts
from app.services.enrichment.source_discovery import discover_reputable_sources, hits_to_url_blocks

from app.services.evidence.ingestion_service import EvidenceIngestionService

from app.services.ingestion.canonicalization_service import CanonicalizationService

from app.services.ingestion.claim_normalization import normalize_claim_text

from app.services.ingestion.duplicate_detection_service import DuplicateDetectionService

from app.services.ingestion.pipeline_audit import IngestionPipelineAudit

logger = logging.getLogger(__name__)

_TERMINAL = frozenset(

    {

        ProcessingStatus.awaiting_moderation,

        ProcessingStatus.completed,

        ProcessingStatus.rejected,

        ProcessingStatus.revision_requested,

    }

)

_EMPTY_DIGEST_PROMPT = (

    "ARCHIVE EVIDENCE: no reputable web sources were retrieved for this claim.\n"

    "Assess the claim using well-established public knowledge (markets, science, units, etc.). "

    "Do not invent URLs or studies. Set evidence_quality between 0.1 and 0.35 to reflect "

    "the empty source set. Choose supported or refuted when the facts are clear; use truth_label "

    "unclear only when genuinely uncertain (target: rare edge cases)."

)

def _provisional_verdict_from_scores(scores: dict[str, Any]) -> dict[str, Any]:

    aggregate = float(scores.get("aggregate", 0.5) or 0.5)

    controversy = float(scores.get("controversy_hint", 0.0) or 0.0)

    label = str(scores.get("truth_label", "")).strip().lower()

    summary = (

        f"Assessment (confidence {aggregate:.0%}): no reputable web sources were retrieved. "

        f"Automated truth status: {label or 'pending'} from model scores."

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

    if has_corpus_evidence:

        return ""

    rationale = str(scores.get("rationale", "")).strip()

    if rationale:

        return rationale

    return (

        "No reputable web sources were retrieved for this assessment. "

        "A moderator can attach sources or re-run enrichment manually."

    )

async def _run_pipeline(pending_id: UUID) -> None:

    """Execute embedding, dedupe, canonicalization, retrieval, and verdict."""

    settings = get_settings()

    pipeline = get_enrichment_pipeline_config()

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

            if pending.embedding is not None:
                vec = list(pending.embedding)
                emb_model = pending.embedding_model
            else:
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

            ingestion_svc = EvidenceIngestionService(session, crawl=pipeline.crawl)

            canonical = pending.canonical_candidate_text or pending.raw_claim_text

            retrieval_cfg = pipeline.retrieval

            crawl_task = ingestion_svc.process_pending_jobs(

                pending_id,

                provider=provider,

                budget_scope=f"pending:{pending_id}",

            )

            source_cfg = pipeline.sources

            reputable_task = discover_reputable_sources(

                canonical,

                cfg=source_cfg,

            )

            if pipeline.retrieval.borrow_from_similar_claims:

                evidence_task = repo.evidence_for_similar_claims(

                    vec,

                    limit=retrieval_cfg.evidence_line_limit,

                    min_similarity=retrieval_cfg.min_similarity,

                    exclude_claim_id=pending.linked_claim_id,

                    similar_claim_limit=retrieval_cfg.similar_claim_search_limit,

                    max_similar_claims=retrieval_cfg.max_similar_claims,

                )

                artifacts, evidence_ctx, reputable_hits = await asyncio.gather(

                    crawl_task, evidence_task, reputable_task

                )

            else:

                artifacts, reputable_hits = await asyncio.gather(crawl_task, reputable_task)

                evidence_ctx = []

            reputable_blocks = hits_to_url_blocks(list(reputable_hits))

            url_blocks = reputable_blocks + url_blocks_from_artifacts(

                artifacts,

                excerpt_chars=pipeline.crawl.artifact_excerpt_chars,

            )

            ctx_bundle = build_evidence_context(

                evidence_rows=list(evidence_ctx),

                url_blocks=url_blocks,

                retrieval=retrieval_cfg,

                empty_digest_prompt=_EMPTY_DIGEST_PROMPT,

            )

            run_at = datetime.now(tz=UTC)

            provenance = build_enrichment_provenance(

                pending=pending,

                canonical_claim_text=canonical,

                line_map=ctx_bundle.line_map,

                embedding_model=emb_model,

                embedding_version=settings.embedding_version,

                has_corpus_evidence=ctx_bundle.has_corpus_evidence,

                url_artifact_ids=[

                    str(b.get("artifact_id")) for b in url_blocks if b.get("artifact_id")

                ],

                borrowed_evidence_ids=[

                    str(ctx_bundle.line_map[k].get("evidence_id"))

                    for k in sorted(ctx_bundle.line_map)

                    if ctx_bundle.line_map[k].get("kind") == "db_evidence"

                    and ctx_bundle.line_map[k].get("evidence_id")

                ],

                reputable_source_urls=[str(b.get("url")) for b in reputable_blocks if b.get("url")],

                assessment_run_at=run_at,

            )

            scores, verdict = await run_assessment_stage(

                provider,

                claim=canonical,

                context=ctx_bundle.context,

                digest=ctx_bundle.digest,

                has_corpus_evidence=ctx_bundle.has_corpus_evidence,

                ai=pipeline.ai,

                provisional_verdict_from_scores=_provisional_verdict_from_scores,

            )

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

            await ai_repo.add_analysis(

                target_type="pending_claim",

                target_id=pending.id,

                model_name=settings.ai_model_reasoning,

                provider=provider.name,

                analysis_type="structured_verdict",

                generated_text=str(verdict.get("verdict_summary", "")),

                structured_payload={

                    "verdict": verdict,

                    "line_map": ctx_bundle.line_map,

                    "provenance": provenance,

                },

                confidence=float(verdict.get("confidence_hint", 0.5) or 0.5),

                created_by_job="enrichment",

            )

            summary = resolve_research_summary(

                verdict=verdict,

                scores=scores,

                has_corpus_evidence=ctx_bundle.has_corpus_evidence,

                ai=pipeline.ai,

                fallback_from_scores=_research_summary_from_scores,

            )

            if not summary and not pipeline.ai.skip_evidence_summary_call:

                if ctx_bundle.has_corpus_evidence:

                    summary_input = (

                        f"CLAIM UNDER REVIEW:\n{canonical}\n\n"

                        f"NUMBERED EVIDENCE LINES:\n{ctx_bundle.context}"

                    )

                    summary = await provider.summarize_evidence(summary_input)

                else:

                    summary = _research_summary_from_scores(

                        scores, has_corpus_evidence=False

                    )

            pending.ai_summary = summary or str(verdict.get("verdict_summary", ""))

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

                    "reputable_sources": len(reputable_blocks),

                    "pipeline": {

                        "combined_assessment": pipeline.ai.use_combined_assessment,

                        "parallel_fetches": pipeline.crawl.parallel_fetches,

                    },

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

    pid = UUID(str(pending_id))

    async with enrichment_task_lock(pid) as acquired:

        if not acquired:

            return

        await _run_pipeline(pid)

def run_pending_enrichment(pending_id: str) -> None:

    asyncio.run(enrich_pending_claim_async(pending_id))
