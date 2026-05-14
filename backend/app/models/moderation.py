"""Moderation actions and immutable audit trail."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid


class ModerationActionType(str, enum.Enum):
    """Moderator workflow verbs."""

    approve_claim = "approve_claim"
    reject_claim = "reject_claim"
    request_revision = "request_revision"
    merge_duplicates = "merge_duplicates"
    archive_claim = "archive_claim"
    update_scores = "update_scores"
    flag_evidence = "flag_evidence"
    remove_evidence = "remove_evidence"
    restore_evidence = "restore_evidence"


class ModerationAction(Base):
    """Single immutable moderation decision."""

    __tablename__ = "moderation_actions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    actor_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action_type: Mapped[ModerationActionType] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
