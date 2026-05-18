"""Evidence search and artifact DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceSearchHitResponse(BaseModel):
    """Semantic retrieval hit over an evidence chunk."""

    chunk_id: UUID
    chunk_text: str
    similarity: float
    artifact_id: UUID | None
    artifact_url: str | None
    artifact_title: str | None
    publisher: str | None
    retrieval_source: str | None


class EvidenceSearchResponse(BaseModel):
    """Search results envelope."""

    query: str
    hits: list[EvidenceSearchHitResponse]


class EvidenceArtifactSummary(BaseModel):
    """Public artifact provenance summary."""

    id: UUID
    url: str
    title: str
    publisher: str | None
    source_type: str
    retrieval_timestamp: datetime
    retrieval_source: str
    chunk_count: int = 0
    citations: list[dict[str, str]] | None = None

    model_config = {"from_attributes": True}
