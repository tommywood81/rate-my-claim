"""Persistence for deduplicated evidence artifacts and chunks."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.evidence_artifact import EvidenceArtifact
from app.models.evidence_chunk import EvidenceChunk
from app.repositories.base import RepositoryBase


class EvidenceArtifactRepository(RepositoryBase):
    """Artifacts and chunk storage."""

    async def get_by_url(self, url: str) -> EvidenceArtifact | None:
        """Load artifact by canonical URL."""
        stmt = select(EvidenceArtifact).where(EvidenceArtifact.url == url)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, artifact_id: UUID) -> EvidenceArtifact | None:
        """Load artifact with chunks."""
        stmt = (
            select(EvidenceArtifact)
            .options(selectinload(EvidenceArtifact.chunks))
            .where(EvidenceArtifact.id == artifact_id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_content_hash(self, content_hash: str) -> EvidenceArtifact | None:
        """Find artifact with identical content hash."""
        stmt = select(EvidenceArtifact).where(EvidenceArtifact.content_hash == content_hash)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_artifact(
        self,
        *,
        url: str,
        content_hash: str,
        source_type: str,
        title: str,
        publisher: str | None,
        authors: str | None,
        publication_date: datetime | None,
        summary: str | None,
        cleaned_content: str | None,
        citations: list | None,
        extraction_metadata: dict | None,
        retrieval_timestamp: datetime,
        retrieval_source: str,
        embedding: list[float] | None = None,
        embedding_model: str | None = None,
        embedding_version: str | None = None,
    ) -> EvidenceArtifact:
        """Insert a new artifact row."""
        row = EvidenceArtifact(
            url=url,
            content_hash=content_hash,
            source_type=source_type,
            title=title,
            publisher=publisher,
            authors=authors,
            publication_date=publication_date,
            summary=summary,
            cleaned_content=cleaned_content,
            citations=citations,
            extraction_metadata=extraction_metadata,
            retrieval_timestamp=retrieval_timestamp,
            retrieval_source=retrieval_source,
            embedding=embedding,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def replace_chunks(
        self,
        *,
        artifact_id: UUID,
        chunks: list[tuple[int, str, list[float] | None, str | None, str | None]],
    ) -> list[EvidenceChunk]:
        """Replace all chunks for an artifact (index, text, embedding, model, version)."""
        existing = await self._session.execute(
            select(EvidenceChunk).where(EvidenceChunk.artifact_id == artifact_id)
        )
        for row in existing.scalars().all():
            await self._session.delete(row)
        out: list[EvidenceChunk] = []
        now = datetime.now(tz=UTC)
        for idx, text, emb, emb_model, emb_ver in chunks:
            chunk = EvidenceChunk(
                artifact_id=artifact_id,
                evidence_id=None,
                chunk_index=idx,
                text=text,
                embedding=emb,
                embedding_model=emb_model,
                embedding_version=emb_ver,
                created_at=now,
            )
            self._session.add(chunk)
            out.append(chunk)
        await self._session.flush()
        return out

    async def semantic_search_chunks(
        self,
        embedding: list[float],
        *,
        limit: int = 20,
    ) -> list[tuple[EvidenceChunk, EvidenceArtifact | None, float]]:
        """Return chunks ordered by cosine similarity (distance ascending)."""
        dist = EvidenceChunk.embedding.cosine_distance(embedding)  # type: ignore[union-attr]
        stmt = (
            select(EvidenceChunk, EvidenceArtifact, dist)
            .outerjoin(EvidenceArtifact, EvidenceChunk.artifact_id == EvidenceArtifact.id)
            .where(EvidenceChunk.embedding.is_not(None))
            .order_by(dist)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(chunk, artifact, float(dist_val)) for chunk, artifact, dist_val in rows]
