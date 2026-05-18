"""Deduplicated fetched documents with provenance (pre- or post-claim attachment)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.evidence_chunk import EvidenceChunk


class EvidenceArtifact(Base, TimestampMixin):
    """Normalized external document stored once per canonical URL."""

    __tablename__ = "evidence_artifacts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authors: Mapped[str | None] = mapped_column(String(512), nullable=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    extraction_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retrieval_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieval_source: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    chunks: Mapped[list[EvidenceChunk]] = relationship(
        "EvidenceChunk",
        back_populates="artifact",
        cascade="all, delete-orphan",
        foreign_keys="EvidenceChunk.artifact_id",
    )
