"""Curated RSS/API publication feeds for evidence ingestion."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class EvidenceSourceFeed(Base, TimestampMixin):
    """Trusted feed or API endpoint for scheduled evidence ingestion."""

    __tablename__ = "evidence_source_feeds"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    feed_type: Mapped[str] = mapped_column(String(32), nullable=False, default="rss")
    publisher_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feed_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
