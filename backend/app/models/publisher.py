"""Publisher credibility profiles."""

from uuid import UUID

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class PublisherProfile(Base, TimestampMixin):
    """Structured publisher metadata for evidence scoring."""

    __tablename__ = "publisher_profiles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    publisher_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    bias_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expertise_domains: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    review_status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
