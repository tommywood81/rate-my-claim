"""Phase 11: cross-cutting API integration smoke tests."""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

from tests.conftest import PG_INTEGRATION, PG_SKIP_REASON

pytestmark = pytest.mark.skipif(not PG_INTEGRATION, reason=PG_SKIP_REASON)


@pytest.mark.asyncio
async def test_public_api_surface(async_client: AsyncClient) -> None:
    """Core read endpoints respond for a healthy stack."""
    health = await async_client.get("/health")
    assert health.status_code == 200

    ready = await async_client.get("/ready")
    assert ready.status_code == 200

    metrics = await async_client.get("/metrics")
    assert metrics.status_code == 200
    assert "rmc_" in metrics.text

    claims = await async_client.get("/api/v1/claims?limit=3")
    assert claims.status_code == 200
    assert claims.json()["success"] is True


@pytest.mark.asyncio
async def test_search_graph_timeline_flow(async_client: AsyncClient) -> None:
    """Search, graph, and timeline work end-to-end for an existing claim."""
    list_res = await async_client.get("/api/v1/claims?limit=1")
    data = list_res.json()["data"]
    if not data:
        pytest.skip("no claims — run seed_development.py")
    slug = data[0]["public_slug"]

    search = await async_client.get("/api/v1/search/claims", params={"q": "health", "limit": 5})
    assert search.status_code == 200

    graph = await async_client.get(
        f"/api/v1/claims/{slug}/graph",
        params={"depth": 1, "include_evidence_clusters": "true"},
    )
    assert graph.status_code == 200
    g = graph.json()["data"]
    assert g["focus_claim_id"]
    assert isinstance(g["nodes"], list)

    timeline = await async_client.get(f"/api/v1/claims/{slug}/timeline")
    assert timeline.status_code == 200
    assert isinstance(timeline.json()["data"]["events"], list)


@pytest.mark.asyncio
async def test_csrf_and_claim_detail(async_client: AsyncClient) -> None:
    """CSRF cookie issues and claim detail returns evidence structure."""
    csrf = await async_client.get("/api/v1/csrf")
    assert csrf.status_code == 200

    list_res = await async_client.get("/api/v1/claims?limit=1")
    slug = list_res.json()["data"][0]["public_slug"]
    detail = await async_client.get(f"/api/v1/claims/{slug}")
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert "evidence_supporting" in body
    assert "ai_analyses" in body


@pytest.mark.asyncio
async def test_moderator_can_list_pending(async_client: AsyncClient, seed_password: str) -> None:
    """Moderator RBAC allows moderation queue access."""
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "seed_moderator", "password": seed_password},
    )
    if login.status_code != 200:
        pytest.skip("seed_moderator not available")
    queue = await async_client.get("/api/v1/moderation/pending-claims")
    assert queue.status_code == 200
