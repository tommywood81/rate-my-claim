"""Claim history timeline events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

TimelineEventType = Literal[
    "confidence_evolution",
    "moderation",
    "evidence",
    "contradiction_emergence",
    "freshness_decay",
]


class TimelineEvent(BaseModel):
    """Single point on the claim history axis."""

    id: str
    event_type: TimelineEventType
    timestamp: datetime
    title: str
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ClaimTimelineResponse(BaseModel):
    """Chronological claim history (oldest first)."""

    claim_id: UUID
    events: list[TimelineEvent]
