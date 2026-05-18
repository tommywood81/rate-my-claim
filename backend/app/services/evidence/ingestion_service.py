"""Orchestrate URL/RSS evidence fetch, chunking, embedding, and artifact storage."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
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
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._artifacts = EvidenceArtifactRepository(session)
        self._jobs = IngestionJobRepository(session)
        self._extractor = extractor or HtmlExtractor()

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

        digest = content_hash(url=normalized, text=doc.text)
        by_hash = await self._artifacts.get_by_content_hash(digest)
        if by_hash:
            return by_hash

        ai = provider or get_ai_provider(budget_scope=budget_scope)
        doc_vec, doc_model = await ai.generate_embedding(doc.text[:8000])
        chunks = chunk_text(
            doc.text,
            chunk_size=self._settings.evidence_chunk_size,
            overlap=self._settings.evidence_chunk_overlap,
        )
        chunk_rows: list[tuple[int, str, list[float] | None, str | None, str | None]] = []
        for idx, piece in enumerate(chunks):
            vec, emb_model = await ai.generate_embedding(piece[:8000])
            chunk_rows.append(
                (idx, piece, vec, emb_model, self._settings.embedding_version)
            )

        summary = doc.text[:500].strip() if doc.text else None
        artifact = await self._artifacts.create_artifact(
            url=normalized,
            content_hash=digest,
            source_type=source_type,
            title=doc.title,
            publisher=doc.publisher,
            authors=doc.authors,
            publication_date=doc.publication_date,
            summary=summary,
            cleaned_content=doc.text,
            citations=doc.citations,
            extraction_metadata=doc.extraction_metadata,
            retrieval_timestamp=doc.retrieval_timestamp,
            retrieval_source=retrieval_source or doc.retrieval_source,
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
            extra={"artifact_id": str(artifact.id), "url": normalized, "chunks": len(chunk_rows)},
        )
        loaded = await self._artifacts.get_by_id(artifact.id)
        return loaded or artifact

    async def process_job(
        self,
        job: IngestionJob,
        *,
        provider: BaseAIProvider | None = None,
        budget_scope: str | "evidence_job",
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

    async def process_pending_jobs(
        self,
        pending_id: UUID,
        *,
        provider: BaseAIProvider | None = None,
        budget_scope: str = "pending",
    ) -> list[EvidenceArtifact]:
        """Process all ingestion jobs for a pending claim."""
        artifacts: list[EvidenceArtifact] = []
        jobs = await self._jobs.list_for_pending(pending_id)
        for job in jobs:
            status = IngestionJobStatus(str(job.status))
            if status == IngestionJobStatus.succeeded and job.artifact_id:
                loaded = await self._artifacts.get_by_id(job.artifact_id)
                if loaded:
                    artifacts.append(loaded)
                continue
            if status in {IngestionJobStatus.failed, IngestionJobStatus.running}:
                continue
            result = await self.process_job(
                job,
                provider=provider,
                budget_scope=f"{budget_scope}:{pending_id}",
            )
            if result:
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
