"""Assemble unified claim history timelines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ClaimRelationship, ClaimRevision, RelationshipType
from app.models.evidence import Evidence
from app.repositories.graph_repository import GraphRepository
from app.repositories.platform_repository import PlatformRepository
from app.schemas.timeline import ClaimTimelineResponse, TimelineEvent


class ClaimTimelineService:
    """Merge revisions, moderation, evidence, contradictions, and freshness signals."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._graphs = GraphRepository(session)
        self._platform = PlatformRepository(session)

    async def build_timeline(self, claim: Claim, *, limit: int = 200) -> ClaimTimelineResponse:
        """Return chronological events (oldest first)."""
        events: list[TimelineEvent] = []

        revisions = await self._graphs.list_revisions(claim.id, limit=limit)
        for rev in revisions:
            if rev.previous_confidence is not None or rev.new_confidence is not None:
                events.append(
                    TimelineEvent(
                        id=f"rev-conf-{rev.id}",
                        event_type="confidence_evolution",
                        timestamp=rev.created_at,
                        title="Confidence updated",
                        description=rev.explanation,
                        payload={
                            "previous_confidence": rev.previous_confidence,
                            "new_confidence": rev.new_confidence,
                            "previous_status": rev.previous_status,
                            "new_status": rev.new_status,
                        },
                    )
                )
            elif rev.previous_status or rev.new_status:
                events.append(
                    TimelineEvent(
                        id=f"rev-status-{rev.id}",
                        event_type="confidence_evolution",
                        timestamp=rev.created_at,
                        title="Status changed",
                        description=rev.explanation,
                        payload={
                            "previous_status": rev.previous_status,
                            "new_status": rev.new_status,
                        },
                    )
                )

        for action in await self._platform.list_moderation_for_target(claim.id, limit=limit):
            events.append(
                TimelineEvent(
                    id=f"mod-{action.id}",
                    event_type="moderation",
                    timestamp=action.created_at,
                    title=action.action_type.replace("_", " ").title(),
                    description=action.explanation,
                    payload={
                        "action_type": action.action_type,
                        "target_type": action.target_type,
                        "payload": action.payload,
                    },
                )
            )

        evidence_rows = list(
            (
                await self._session.execute(
                    select(Evidence).where(Evidence.claim_id == claim.id).order_by(Evidence.created_at)
                )
            )
            .scalars()
            .all()
        )
        for ev in evidence_rows:
            ts = ev.retrieval_timestamp or ev.created_at
            stance = ev.stance.value if hasattr(ev.stance, "value") else str(ev.stance)
            events.append(
                TimelineEvent(
                    id=f"ev-{ev.id}",
                    event_type="evidence",
                    timestamp=ts,
                    title=f"Evidence added: {ev.title[:80]}",
                    description=ev.summary,
                    payload={
                        "evidence_id": str(ev.id),
                        "stance": stance,
                        "credibility_score": ev.credibility_score,
                        "publisher": ev.publisher,
                    },
                )
            )

        relationships = await self._graphs.list_relationships_for_claim(
            claim.id,
            relationship_types=[RelationshipType.contradiction],
            limit=limit,
        )
        claims_map = await self._load_claims(
            list(
                {
                    r.source_claim_id
                    for r in relationships
                }
                | {
                    r.target_claim_id
                    for r in relationships
                }
            )
        )
        for rel in relationships:
            other_id = (
                rel.target_claim_id if rel.source_claim_id == claim.id else rel.source_claim_id
            )
            other = claims_map.get(other_id)
            label = _truncate(other.canonical_claim_text if other else "Related claim", 60)
            events.append(
                TimelineEvent(
                    id=f"contradiction-{rel.id}",
                    event_type="contradiction_emergence",
                    timestamp=rel.created_at,
                    title="Contradiction linked",
                    description=rel.explanation or label,
                    payload={
                        "relationship_id": str(rel.id),
                        "other_claim_id": str(other_id),
                        "other_slug": other.public_slug if other else None,
                        "strength": rel.strength,
                    },
                )
            )

        events.extend(self._freshness_decay_events(claim, evidence_rows))

        events.sort(key=lambda e: e.timestamp)
        if len(events) > limit:
            events = events[-limit:]

        return ClaimTimelineResponse(claim_id=claim.id, events=events)

    def _freshness_decay_events(self, claim: Claim, evidence: list[Evidence]) -> list[TimelineEvent]:
        """Derive freshness decay signals from evidence age and claim review timestamps."""
        out: list[TimelineEvent] = []
        now = datetime.now(tz=UTC)
        if claim.created_at:
            out.append(
                TimelineEvent(
                    id=f"freshness-baseline-{claim.id}",
                    event_type="freshness_decay",
                    timestamp=claim.created_at,
                    title="Freshness baseline",
                    description="Claim published; initial freshness scoring applies.",
                    payload={"freshness_score": claim.freshness_score},
                )
            )
        if claim.last_reviewed_at:
            out.append(
                TimelineEvent(
                    id=f"freshness-review-{claim.id}",
                    event_type="freshness_decay",
                    timestamp=claim.last_reviewed_at,
                    title="Review completed",
                    description="Moderator review may adjust freshness weighting.",
                    payload={"freshness_score": claim.freshness_score},
                )
            )
        for ev in evidence:
            ts = ev.retrieval_timestamp or ev.created_at
            if ts is None:
                continue
            age_days = (now - ts).days
            if age_days >= 30:
                decay = max(0.0, 1.0 - age_days / 365.0)
                out.append(
                    TimelineEvent(
                        id=f"freshness-ev-{ev.id}",
                        event_type="freshness_decay",
                        timestamp=ts + timedelta(days=30),
                        title="Evidence aging signal",
                        description=f"Source age exceeds 30 days; decay factor ~{decay:.2f}.",
                        payload={
                            "evidence_id": str(ev.id),
                            "age_days": age_days,
                            "estimated_decay": round(decay, 3),
                        },
                    )
                )
        return out

    async def _load_claims(self, claim_ids: list[UUID]) -> dict[UUID, Claim]:
        if not claim_ids:
            return {}
        stmt = select(Claim).where(Claim.id.in_(claim_ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {r.id: r for r in rows}


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else f"{text[: max_len - 1]}…"
