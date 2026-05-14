"""Cursor encode/decode helpers for keyset pagination."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ClaimCursor:
    """Stable ordering key for claim lists."""

    created_at: datetime
    claim_id: UUID


def encode_cursor(c: ClaimCursor) -> str:
    """Serialize cursor to URL-safe opaque string."""
    raw = json.dumps(
        {"created_at": c.created_at.isoformat(), "id": str(c.claim_id)},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(value: str | None) -> ClaimCursor | None:
    """Parse cursor or return None if invalid."""
    if not value:
        return None
    pad = "=" * (-len(value) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(value + pad).decode("utf-8"))
        return ClaimCursor(
            created_at=datetime.fromisoformat(data["created_at"]),
            claim_id=UUID(data["id"]),
        )
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
