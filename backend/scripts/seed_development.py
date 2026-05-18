"""Load development fixtures into PostgreSQL (Phase 2 verification).

Run inside the backend container after migrations::

    SEED_DEVELOPMENT=true python scripts/seed_development.py

Idempotent: skips if ``seed_admin`` user already exists.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import random
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.claim import Claim, ClaimStatus, RelationshipType
from app.models.evidence import Evidence, EvidenceSourceType, EvidenceStance
from app.models.user import User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.graph_repository import GraphRepository
from app.repositories.platform_repository import PlatformRepository
from app.utils.slug import public_slug_for_claim

logger = logging.getLogger(__name__)


def _unit_embedding(dim: int = 1536) -> list[float]:
    """Return a normalized random vector suitable for cosine indexing."""
    raw = [random.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


async def _run() -> None:
    """Insert seed rows when SEED_DEVELOPMENT is truthy."""
    if os.environ.get("SEED_DEVELOPMENT", "").lower() not in {"1", "true", "yes"}:
        logger.info("skip_seed_set_SEED_DEVELOPMENT_true")
        return

    settings = get_settings()
    async with AsyncSessionLocal() as session:
        users_table = await session.scalar(text("SELECT to_regclass('public.users')"))
        if users_table is None:
            logger.error(
                "schema_missing_apply_migrations_first: "
                "docker compose exec backend alembic upgrade head"
            )
            raise SystemExit(1)

        existing = await session.scalar(select(User.id).where(User.username == "seed_admin"))
        if existing is not None:
            logger.info("seed_already_applied")
            return

        pwd = os.environ.get("SEED_PASSWORD", "SeedDev!ChangeMe123")
        admin = User(
            id=uuid4(),
            username="seed_admin",
            email="seed-admin@example.local",
            password_hash=get_password_hash(pwd),
            role=UserRole.admin.value,
        )
        mod = User(
            id=uuid4(),
            username="seed_moderator",
            email="seed-mod@example.com",
            password_hash=get_password_hash(pwd),
            role=UserRole.moderator.value,
        )
        session.add_all([admin, mod])
        await session.flush()

        platform = PlatformRepository(session)
        await platform.upsert_publisher(
            publisher_name="Example Press",
            credibility_score=0.72,
            expertise_domains=["science"],
            review_status="approved",
        )

        canonical = "Daily moderate exercise is associated with improved cardiovascular health outcomes."
        claim_id = uuid4()
        slug = public_slug_for_claim(canonical, claim_id)
        emb = _unit_embedding()
        claim = Claim(
            id=claim_id,
            public_slug=slug,
            canonical_claim_text=canonical,
            normalized_claim_text=canonical.lower().strip(),
            embedding=emb,
            embedding_model=settings.embedding_model,
            embedding_version=settings.embedding_version,
            embedding_at=datetime.now(tz=UTC),
            status=ClaimStatus.weak_evidence,
            confidence_score=0.55,
            controversy_score=0.15,
            evidence_score=0.4,
            freshness_score=0.7,
            evidence_count=1,
            created_by=admin.id,
        )
        session.add(claim)
        await session.flush()

        graphs = GraphRepository(session)
        await graphs.add_alias(claim_id=claim_id, alias_text="Exercise benefits cardiovascular health.")
        await graphs.add_revision(
            claim_id=claim_id,
            previous_status=None,
            new_status=ClaimStatus.weak_evidence.value,
            previous_confidence=None,
            new_confidence=claim.confidence_score,
            explanation="Initial seed revision",
            created_by=mod.id,
        )

        ev = Evidence(
            id=uuid4(),
            claim_id=claim_id,
            source_type=EvidenceSourceType.manual_url,
            title="Overview of physical activity and heart disease (seed)",
            url="https://example.com/seed-cardiovascular-exercise",
            publisher="Example Press",
            stance=EvidenceStance.supports,
            credibility_score=0.65,
            summary="Seed evidence row for local hybrid search and UI testing.",
            embedding=_unit_embedding(),
            embedding_model=settings.embedding_model,
            embedding_version=settings.embedding_version,
            retrieval_timestamp=datetime.now(tz=UTC),
            retrieval_source="seed_script",
            created_by=admin.id,
        )
        session.add(ev)

        counter_claim = "High-intensity daily exercise always improves cardiovascular outcomes without exception."
        counter_id = uuid4()
        counter_slug = public_slug_for_claim(counter_claim, counter_id)
        counter = Claim(
            id=counter_id,
            public_slug=counter_slug,
            canonical_claim_text=counter_claim,
            normalized_claim_text=counter_claim.lower().strip(),
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
            created_by=admin.id,
        )
        session.add(counter)
        await session.flush()

        await graphs.add_relationship(
            source_claim_id=claim_id,
            target_claim_id=counter_id,
            relationship_type=RelationshipType.contradiction,
            strength=0.78,
            explanation="Seed contradiction for graph and timeline UI testing.",
        )
        await graphs.add_relationship(
            source_claim_id=claim_id,
            target_claim_id=counter_id,
            relationship_type=RelationshipType.refinement,
            strength=0.4,
            explanation="Seed refinement edge (filtered separately in graph UI).",
        )

        audit = AuditRepository(session)
        await audit.append_system_event(
            event_type="claim_seeded",
            aggregate_type="claim",
            aggregate_id=claim_id,
            payload={"slug": slug, "by": "seed_development"},
        )
        await audit.append_audit_log(
            actor_id=admin.id,
            action="seed_development",
            resource_type="claim",
            resource_id=claim_id,
            details={"slug": slug},
        )

        await platform.append_reputation_event(
            user_id=admin.id,
            delta=1.0,
            reason="seed",
            explanation="Bootstrap seed script",
            reference_type="claim",
            reference_id=claim_id,
        )

        await session.commit()
        logger.info("seed_complete", extra={"claim_slug": slug, "admin": "seed_admin"})


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
