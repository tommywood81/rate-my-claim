"""Claim, pending claim, aliases, revisions, relationships, votes."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.user import User


class ClaimStatus(str, enum.Enum):
    """Lifecycle status for approved claims."""

    verified = "verified"
    disputed = "disputed"
    weak_evidence = "weak_evidence"
    insufficient_evidence = "insufficient_evidence"
    outdated = "outdated"
    archived = "archived"


class ProcessingStatus(str, enum.Enum):
    """Async pipeline state for pending submissions."""

    submitted = "submitted"
    embedding = "embedding"
    duplicate_check = "duplicate_check"
    canonicalizing = "canonicalizing"
    enriching = "enriching"
    awaiting_moderation = "awaiting_moderation"
    revision_requested = "revision_requested"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"


class RelationshipType(str, enum.Enum):
    """Inter-claim graph edge types."""

    duplicate = "duplicate"
    refinement = "refinement"
    dependency = "dependency"
    causal_link = "causal_link"
    contextual_relationship = "contextual_relationship"
    contradiction = "contradiction"


class Claim(Base, TimestampMixin):
    """Approved canonical claim (moderator-promoted from pending)."""

    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    public_slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    canonical_claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_claim_text: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        String(32), nullable=False, default=ClaimStatus.insufficient_evidence
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    controversy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discovery_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evidence_items: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="claim", foreign_keys="Evidence.claim_id"
    )
    aliases: Mapped[list["ClaimAlias"]] = relationship("ClaimAlias", back_populates="claim")
    votes: Mapped[list["ClaimVote"]] = relationship("ClaimVote", back_populates="claim")


class PendingClaim(Base, TimestampMixin):
    """User-submitted claim awaiting moderation and enrichment."""

    __tablename__ = "pending_claims"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    raw_claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_claim_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_candidate_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        String(40), nullable=False, default=ProcessingStatus.submitted
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_candidate_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_by_user: Mapped["User"] = relationship("User", foreign_keys=[submitted_by])


class ClaimAlias(Base, TimestampMixin):
    """Alternate phrasing linked to an approved claim."""

    __tablename__ = "claim_aliases"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    alias_text: Mapped[str] = mapped_column(Text, nullable=False)

    claim: Mapped["Claim"] = relationship("Claim", back_populates="aliases")


class ClaimRevision(Base):
    """Immutable snapshot of moderation or scoring changes."""

    __tablename__ = "claim_revisions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    previous_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimRelationship(Base, TimestampMixin):
    """Directed semantic edge between two approved claims."""

    __tablename__ = "claim_relationships"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    source_claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    target_claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(String(40), nullable=False)
    strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_evidence_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class ClaimVote(Base, TimestampMixin):
    """Per-user discovery vote on an approved claim."""

    __tablename__ = "claim_votes"
    __table_args__ = (UniqueConstraint("claim_id", "user_id", name="uq_claim_vote_user"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)

    claim: Mapped["Claim"] = relationship("Claim", back_populates="votes")
