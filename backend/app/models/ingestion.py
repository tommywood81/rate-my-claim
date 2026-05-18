"""Background ingestion jobs (URLs, RSS, APIs)."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid


class IngestionJobStatus(str, enum.Enum):
    """Job lifecycle."""

    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class IngestionJob(Base):
    """Tracks async fetch and parse work."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    pending_claim_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pending_claims.id", ondelete="CASCADE"), nullable=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="manual_url")
    feed_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    status: Mapped[IngestionJobStatus] = mapped_column(String(32), nullable=False, default=IngestionJobStatus.queued)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
