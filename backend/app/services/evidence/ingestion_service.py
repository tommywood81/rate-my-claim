"""Orchestrate URL/RSS evidence fetch, chunking, embedding, and artifact storage."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enrichment_pipeline_config import CrawlStageConfig, get_enrichment_pipeline_config
from app.models.evidence_artifact import EvidenceArtifact
from app.models.ingestion import IngestionJob, IngestionJobStatus
from app.repositories.evidence_artifact_repository import EvidenceArtifactRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.services.ai.factory import get_ai_provider
from app.services.ai.providers.base import BaseAIProvider
from app.services.evidence.chunking import chunk_text
from app.services.evidence.deduplication import content_hash, normalize_url
from app.services.evidence.html_extractor import HtmlExtractor

logger = logging.getLogger(__name__)


class EvidenceIngestionService:
    """Structured evidence ingestion with provenance and deduplication."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        extractor: HtmlExtractor | None = None,
        crawl: CrawlStageConfig | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._crawl = crawl or get_enrichment_pipeline_config().crawl
        self._artifacts = EvidenceArtifactRepository(session)
        self._jobs = IngestionJobRepository(session)
        self._extractor = extractor or HtmlExtractor(timeout=self._crawl.http_timeout_seconds)

    async def ingest_url(
        self,
        url: str,
        *,
        source_type: str = "manual_url",
        retrieval_source: str | None = None,
        provider: BaseAIProvider | None = None,
        budget_scope: str = "evidence_ingest",
    ) -> EvidenceArtifact:
        """Fetch URL, dedupe, chunk, embed, and persist artifact."""
        normalized = normalize_url(url)
        existing = await self._artifacts.get_by_url(normalized)
        if existing and existing.cleaned_content:
            return existing

        doc = await self._extractor.extract(url)
        if doc.error or not doc.text.strip():
            raise ValueError(doc.error or "empty_extraction")

        text = doc.text[: self._crawl.max_extracted_chars]
        digest = content_hash(url=normalized, text=text)
        by_hash = await self._artifacts.get_by_content_hash(digest)
        if by_hash:
            return by_hash

        ai = provider or get_ai_provider(budget_scope=budget_scope)
        doc_vec: list[float] | None = None
        doc_model: str | None = None
        if self._crawl.embed_document_on_hot_path:
            doc_vec, doc_model = await ai.generate_embedding(text[:8000])

        chunks = chunk_text(
            text,
            chunk_size=self._settings.evidence_chunk_size,
            overlap=self._settings.evidence_chunk_overlap,
        )
        chunk_rows: list[tuple[int, str, list[float] | None, str | None, str | None]] = []
        embed_cap = 0 if self._crawl.skip_chunk_embeddings_on_hot_path else self._crawl.max_chunks_to_embed
        for idx, piece in enumerate(chunks):
            vec: list[float] | None = None
            emb_model: str | None = None
            if embed_cap > 0 and idx < embed_cap:
                vec, emb_model = await ai.generate_embedding(piece[:8000])
            chunk_rows.append((idx, piece, vec, emb_model, self._settings.embedding_version))

        summary = text[:500].strip() if text else None
        artifact = await self._artifacts.create_artifact(
            url=normalized,
            content_hash=digest,
            source_type=source_type,
            title=doc.title,
            publisher=doc.publisher,
            authors=doc.authors,
            publication_date=doc.publication_date,
            citations=doc.citations,
            extraction_metadata=doc.extraction_metadata,
            retrieval_timestamp=doc.retrieval_timestamp,
            retrieval_source=retrieval_source or doc.retrieval_source,
            summary=summary,
            cleaned_content=text,
            embedding=doc_vec,
            embedding_model=doc_model,
            embedding_version=self._settings.embedding_version,
        )
        await self._artifacts.replace_chunks(
            artifact_id=artifact.id,
            chunks=chunk_rows,
        )
        logger.info(
            "evidence_artifact_ingested",
            extra={
                "artifact_id": str(artifact.id),
                "url": normalized,
                "chunks": len(chunk_rows),
                "chunk_embeddings": sum(1 for row in chunk_rows if row[2] is not None),
            },
        )
        loaded = await self._artifacts.get_by_id(artifact.id)
        return loaded or artifact

    async def process_job(
        self,
        job: IngestionJob,
        *,
        provider: BaseAIProvider | None = None,
        budget_scope: str = "evidence_job",
    ) -> EvidenceArtifact | None:
        """Run a single ingestion job to completion."""
        await self._jobs.mark_running(job)
        try:
            artifact = await self.ingest_url(
                job.source_url,
                source_type=job.source_type or "manual_url",
                retrieval_source=f"ingestion_job:{job.id}",
                provider=provider,
                budget_scope=f"{budget_scope}:{job.id}",
            )
            await self._jobs.mark_succeeded(
                job,
                artifact_id=artifact.id,
                result_metadata={
                    "title": artifact.title,
                    "publisher": artifact.publisher,
                    "chunk_count": len(artifact.chunks) if artifact.chunks else 0,
                },
            )
            return artifact
        except Exception as exc:
            await self._jobs.mark_failed(job, error=str(exc))
            logger.warning(
                "ingestion_job_failed",
                extra={"job_id": str(job.id), "error": str(exc)[:200]},
            )
            return None

    async def _process_job_bounded(
        self,
        job: IngestionJob,
        *,
        provider: BaseAIProvider | None,
        budget_scope: str,
        semaphore: asyncio.Semaphore,
    ) -> EvidenceArtifact | None:
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    self.process_job(job, provider=provider, budget_scope=budget_scope),
                    timeout=self._crawl.per_url_timeout_seconds,
                )
            except TimeoutError:
                await self._jobs.mark_failed(job, error="per_url_timeout")
                logger.warning(
                    "ingestion_job_timeout",
                    extra={"job_id": str(job.id), "url": job.source_url[:200]},
                )
                return None

    async def process_pending_jobs(
        self,
        pending_id: UUID,
        *,
        provider: BaseAIProvider | None = None,
        budget_scope: str = "pending",
    ) -> list[EvidenceArtifact]:
        """Process pending URL jobs in parallel with crawl budget limits."""
        artifacts: list[EvidenceArtifact] = []
        jobs = await self._jobs.list_for_pending(pending_id)
        runnable: list[IngestionJob] = []
        for job in jobs[: self._crawl.max_url_jobs]:
            status = IngestionJobStatus(str(job.status))
            if status == IngestionJobStatus.succeeded and job.artifact_id:
                loaded = await self._artifacts.get_by_id(job.artifact_id)
                if loaded:
                    artifacts.append(loaded)
                continue
            if status in {IngestionJobStatus.failed, IngestionJobStatus.running}:
                continue
            runnable.append(job)

        if not runnable:
            return artifacts

        sem = asyncio.Semaphore(self._crawl.parallel_fetches)
        scope = f"{budget_scope}:{pending_id}"

        async def _run_all() -> list[EvidenceArtifact | None]:
            return await asyncio.gather(
                *[
                    self._process_job_bounded(
                        job,
                        provider=provider,
                        budget_scope=scope,
                        semaphore=sem,
                    )
                    for job in runnable
                ]
            )

        try:
            results = await asyncio.wait_for(
                _run_all(),
                timeout=self._crawl.total_crawl_budget_seconds,
            )
        except TimeoutError:
            logger.warning(
                "crawl_budget_exceeded",
                extra={"pending_id": str(pending_id), "jobs": len(runnable)},
            )
            results = []

        for result in results:
            if isinstance(result, EvidenceArtifact):
                artifacts.append(result)
        return artifacts

    @staticmethod
    def artifact_to_context_block(artifact: EvidenceArtifact) -> dict[str, str]:
        """Map artifact to enrichment context block."""
        return {
            "url": artifact.url,
            "title": artifact.title,
            "text": (artifact.cleaned_content or "")[:4000],
            "publisher": artifact.publisher or "",
            "artifact_id": str(artifact.id),
        }
