"""Guest claim submission without authentication."""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 for anonymous submit integration test"


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_guest_can_submit_claim(async_client: AsyncClient) -> None:
    """Unauthenticated user can queue a pending claim with CSRF cookie."""
    csrf = await async_client.get("/api/v1/csrf")
    assert csrf.status_code == 200
    token = csrf.cookies.get("rmc_csrf", "")

    submit = await async_client.post(
        "/api/v1/pending-claims",
        json={"raw_claim_text": "The Earth has one natural satellite."},
        headers={"X-CSRF-Token": token} if token else {},
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["success"] is True
    assert body["meta"]["anonymous"] is True
    assert body["data"]["id"]
