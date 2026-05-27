"""Public claim submit accepts claim text only (no user-supplied URLs)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_submit_rejects_source_urls_in_body(async_client: AsyncClient) -> None:
    csrf = await async_client.get("/api/v1/csrf")
    assert csrf.status_code == 200
    token = csrf.cookies.get("rmc_csrf", "")

    submit = await async_client.post(
        "/api/v1/pending-claims",
        json={
            "raw_claim_text": "The Earth has one natural satellite.",
            "source_urls": ["https://example.com"],
        },
        headers={"X-CSRF-Token": token} if token else {},
    )
    assert submit.status_code == 422
