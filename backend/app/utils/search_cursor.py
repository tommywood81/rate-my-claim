"""Cursor helpers for hybrid search pagination."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchPageCursor:
    """Offset into a cached ranked result list for a fixed query fingerprint."""

    offset: int
    query_key: str


def encode_search_cursor(c: SearchPageCursor) -> str:
    """Serialize search page cursor."""
    raw = json.dumps({"o": c.offset, "k": c.query_key}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_search_cursor(value: str | None) -> SearchPageCursor | None:
    """Parse search cursor."""
    if not value:
        return None
    pad = "=" * (-len(value) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(value + pad).decode("utf-8"))
        return SearchPageCursor(offset=int(data["o"]), query_key=str(data["k"]))
    except (ValueError, KeyError, json.JSONDecodeError, TypeError):
        return None
