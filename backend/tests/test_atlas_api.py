"""Atlas API smoke tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_atlas_claims_returns_200() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/atlas/claims")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert "points" in body["data"]
    for pt in body["data"]["points"]:
        assert pt["truth_label"] in ("supported", "refuted", "unclear")
