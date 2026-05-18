"""Semantic search over evidence chunks and artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.evidence_artifact_repository import EvidenceArtifactRepository
from app.services.ai.factory import get_ai_provider


@dataclass
class EvidenceSearchHit:
    """Single retrieval result with provenance."""

    chunk_id: UUID
    chunk_text: str
    similarity: float
    artifact_id: UUID | None
    artifact_url: str | None
    artifact_title: str | None
    publisher: str | None
    retrieval_source: str | None


class EvidenceSemanticRetrieval:
    """pgvector search over stored evidence chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self._artifacts = EvidenceArtifactRepository(session)

    async def search(self, query: str, *, limit: int = 20, budget_scope: str = "evidence_search") -> list[EvidenceSearchHit]:
        """Embed query and return ranked chunk hits."""
        provider = get_ai_provider(budget_scope=budget_scope)
        vec, _ = await provider.generate_embedding(query[:8000])
        rows = await self._artifacts.semantic_search_chunks(vec, limit=limit)
        hits: list[EvidenceSearchHit] = []
        for chunk, artifact, dist in rows:
            sim = max(0.0, 1.0 - float(dist))
            hits.append(
                EvidenceSearchHit(
                    chunk_id=chunk.id,
                    chunk_text=chunk.text,
                    similarity=sim,
                    artifact_id=artifact.id if artifact else chunk.artifact_id,
                    artifact_url=artifact.url if artifact else None,
                    artifact_title=artifact.title if artifact else None,
                    publisher=artifact.publisher if artifact else None,
                    retrieval_source=artifact.retrieval_source if artifact else None,
                )
            )
        return hits
