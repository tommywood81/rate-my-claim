"""Shared API response and pagination contracts."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorMeta(BaseModel):
    """Cursor pagination metadata."""

    next_cursor: str | None = None
    previous_cursor: str | None = None
    has_more: bool = False


class SuccessEnvelope(BaseModel, Generic[T]):
    """Standard success wrapper."""

    success: bool = True
    data: T
    meta: dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    """Standard error payload."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Standard error wrapper."""

    success: bool = False
    error: ErrorDetail
