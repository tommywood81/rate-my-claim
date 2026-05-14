"""Evidence rows linked to approved claims."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.claim import Claim


class EvidenceStance(str, enum.Enum):
    """How evidence relates to the claim."""

    supports = "supports"
    contradicts = "contradicts"
    contextualizes = "contextualizes"


class EvidenceSourceType(str, enum.Enum):
    """Provenance channel for evidence."""

    manual_url = "manual_url"
    rss = "rss"
    api = "api"
    user_submission = "user_submission"
    moderator = "moderator"


class Evidence(Base, TimestampMixin):
    """Structured evidence record with optional semantic embedding."""

    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[EvidenceSourceType] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authors: Mapped[str | None] = mapped_column(String(512), nullable=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    stance: Mapped[EvidenceStance] = mapped_column(String(32), nullable=False)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieval_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extraction_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    claim: Mapped["Claim"] = relationship("Claim", back_populates="evidence_items", foreign_keys=[claim_id])
