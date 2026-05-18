"""Add demo graph edges to the seed exercise claim (idempotent).

Run after ``seed_development.py`` when ``seed_already_applied`` skipped graph edges::

    docker compose exec backend python scripts/seed_graph_demo.py
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import random
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.claim import Claim, ClaimRelationship, ClaimStatus, RelationshipType
from app.repositories.graph_repository import GraphRepository
from app.utils.slug import public_slug_for_claim

logger = logging.getLogger(__name__)


def _unit_embedding(dim: int = 1536) -> list[float]:
    raw = [random.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


async def _run() -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        claim = await session.scalar(
            select(Claim).where(
                Claim.canonical_claim_text.ilike("%moderate exercise%"),
                Claim.deleted_at.is_(None),
            )
        )
        if claim is None:
            logger.warning("exercise_seed_claim_not_found")
            return

        existing = await session.scalar(
            select(ClaimRelationship.id).where(
                ClaimRelationship.source_claim_id == claim.id,
                ClaimRelationship.relationship_type == RelationshipType.contradiction.value,
            )
        )
        if existing is not None:
            logger.info("graph_demo_already_applied", extra={"claim_id": str(claim.id)})
            return

        graphs = GraphRepository(session)
        counter_text = (
            "High-intensity daily exercise always improves cardiovascular outcomes without exception."
        )
        counter_id = uuid4()
        counter = Claim(
            id=counter_id,
            public_slug=public_slug_for_claim(counter_text, counter_id),
            canonical_claim_text=counter_text,
            normalized_claim_text=counter_text.lower().strip(),
            embedding=_unit_embedding(),
            embedding_model=settings.embedding_model,
            embedding_version=settings.embedding_version,
            embedding_at=datetime.now(tz=UTC),
            status=ClaimStatus.disputed,
            confidence_score=0.35,
            controversy_score=0.72,
            evidence_score=0.25,
            freshness_score=0.55,
            evidence_count=0,
            created_by=claim.created_by,
        )
        session.add(counter)
        await session.flush()

        await graphs.add_relationship(
            source_claim_id=claim.id,
            target_claim_id=counter_id,
            relationship_type=RelationshipType.contradiction,
            strength=0.78,
            explanation="Demo contradiction for graph UI testing.",
        )
        await graphs.add_relationship(
            source_claim_id=claim.id,
            target_claim_id=counter_id,
            relationship_type=RelationshipType.refinement,
            strength=0.4,
            explanation="Demo refinement edge for graph filters.",
        )
        await session.commit()
        logger.info(
            "graph_demo_complete",
            extra={"source_slug": claim.public_slug, "counter_slug": counter.public_slug},
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if os.environ.get("ALLOW_GRAPH_DEMO_SEED", "true").lower() in {"0", "false", "no"}:
        logger.info("skip_set_ALLOW_GRAPH_DEMO_SEED_true")
        return
    asyncio.run(_run())


if __name__ == "__main__":
    main()
