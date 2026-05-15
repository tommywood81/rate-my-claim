"""Phase 2: pgvector similarity against a live PostgreSQL (opt-in)."""

from __future__ import annotations

import math
import os
import random
from uuid import uuid4

import pytest
from sqlalchemy import select, text

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_PG_INTEGRATION") != "1",
    reason="Set RUN_PG_INTEGRATION=1 and DATABASE_URL to a reachable Postgres with pgvector",
)


@pytest.mark.asyncio
async def test_cosine_distance_query() -> None:
    """Insert two claims with embeddings and verify ORDER BY embedding <=> query works."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models.claim import Claim, ClaimStatus
    from app.core.config import Settings

    url = os.environ.get("DATABASE_URL", "")
    if not url or "+asyncpg" not in url:
        pytest.skip("DATABASE_URL must be postgresql+asyncpg URL")

    settings = Settings(secret_key="0" * 40, database_url=url)  # type: ignore[arg-type]
    engine = create_async_engine(str(settings.database_url), echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    def unit(n: int) -> list[float]:
        raw = [random.gauss(0.0, 1.0) for _ in range(n)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    base = unit(1536)
    near = [min(1.0, max(-1.0, base[i] + 0.01 * random.gauss(0, 1))) for i in range(1536)]
    nn = math.sqrt(sum(x * x for x in near)) or 1.0
    near = [x / nn for x in near]

    async with Session() as session:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        cid_a, cid_b = uuid4(), uuid4()
        slug_a, slug_b = f"itest-a-{cid_a.hex[:8]}", f"itest-b-{cid_b.hex[:8]}"
        session.add_all(
            [
                Claim(
                    id=cid_a,
                    public_slug=slug_a,
                    canonical_claim_text="Integration claim A",
                    normalized_claim_text="integration claim a",
                    embedding=base,
                    status=ClaimStatus.insufficient_evidence,
                    created_by=None,
                ),
                Claim(
                    id=cid_b,
                    public_slug=slug_b,
                    canonical_claim_text="Integration claim B",
                    normalized_claim_text="integration claim b",
                    embedding=near,
                    status=ClaimStatus.insufficient_evidence,
                    created_by=None,
                ),
            ]
        )
        await session.commit()

        dist = Claim.embedding.cosine_distance(base)  # type: ignore[union-attr]
        stmt = select(Claim.id, dist.label("d")).where(Claim.id.in_([cid_a, cid_b])).order_by(dist).limit(2)
        rows = (await session.execute(stmt)).all()
        assert rows[0][0] == cid_a
        assert float(rows[0][1]) < float(rows[1][1])

        ra = await session.get(Claim, cid_a)
        rb = await session.get(Claim, cid_b)
        if ra is not None:
            await session.delete(ra)
        if rb is not None:
            await session.delete(rb)
        await session.commit()

    await engine.dispose()
