"""Phase 9: claim graph layout and timeline assembly."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.services.graph.claim_graph_service import layout_nodes

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 for Postgres graph integration tests"


def test_layout_nodes_places_focus_at_origin() -> None:
    focus = uuid4()
    other = uuid4()
    positions = layout_nodes(focus, [focus, other])
    assert positions[focus].x == 0.0
    assert positions[focus].y == 0.0
    assert abs(positions[other].x) > 0 or abs(positions[other].y) > 0


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_graph_and_timeline_endpoints(async_client) -> None:
    """Graph/timeline routes return structured payloads for seeded claims."""
    list_res = await async_client.get("/api/v1/claims?limit=1")
    assert list_res.status_code == 200
    claims = list_res.json()["data"]
    if not claims:
        pytest.skip("no claims in database")
    slug = claims[0]["public_slug"]

    graph_res = await async_client.get(
        f"/api/v1/claims/{slug}/graph",
        params={"depth": 1, "types": "contradiction,dependency"},
    )
    assert graph_res.status_code == 200
    graph = graph_res.json()["data"]
    assert "nodes" in graph
    assert "edges" in graph
    assert graph["focus_claim_id"]
    assert isinstance(graph["available_relationship_types"], list)

    timeline_res = await async_client.get(f"/api/v1/claims/{slug}/timeline")
    assert timeline_res.status_code == 200
    timeline = timeline_res.json()["data"]
    assert timeline["claim_id"]
    assert isinstance(timeline["events"], list)
