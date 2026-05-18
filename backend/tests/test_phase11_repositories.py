"""Phase 11: repository integration tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.claim import Claim
from app.models.claim import RelationshipType
from app.repositories.graph_repository import GraphRepository
from app.repositories.platform_repository import PlatformRepository

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 for repository integration tests"


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_graph_repository_lists_revisions_and_relationships() -> None:
    async with AsyncSessionLocal() as session:
        claim = await session.scalar(select(Claim).where(Claim.deleted_at.is_(None)).limit(1))
        if claim is None:
            pytest.skip("no claims in database")
        graphs = GraphRepository(session)
        revisions = await graphs.list_revisions(claim.id, limit=10)
        assert isinstance(revisions, list)
        rels = await graphs.list_relationships_for_claim(
            claim.id,
            relationship_types=[RelationshipType.contradiction],
            limit=10,
        )
        assert isinstance(rels, list)


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_platform_repository_moderation_for_target() -> None:
    async with AsyncSessionLocal() as session:
        claim = await session.scalar(select(Claim).where(Claim.deleted_at.is_(None)).limit(1))
        if claim is None:
            pytest.skip("no claims in database")
        platform = PlatformRepository(session)
        actions = await platform.list_moderation_for_target(claim.id, limit=20)
        assert isinstance(actions, list)
