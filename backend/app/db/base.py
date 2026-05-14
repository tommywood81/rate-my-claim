"""SQLAlchemy declarative base and mixins."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    type_annotation_map: dict[type, Any] = {}


class TimestampMixin:
    """created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def new_uuid() -> UUID:
    """Return a new random UUID."""
    return uuid4()


def uuid_pk() -> Mapped[UUID]:
    """Primary key column factory for UUID tables."""
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
