"""Phase 11: unit tests for graph, timeline, and ingestion helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.claim import Claim, ClaimStatus
from app.models.evidence import Evidence, EvidenceSourceType, EvidenceStance
from app.services.graph.claim_graph_service import layout_nodes
from app.services.graph.claim_timeline_service import ClaimTimelineService
from app.services.ingestion.claim_normalization import normalize_claim_text
from app.services.search.hybrid_ranking import normalize_batch, safe_float


def test_normalize_claim_text_strips_and_collapses_whitespace() -> None:
    assert normalize_claim_text("  Hello   World  ") == "Hello World"


def test_layout_nodes_unique_positions() -> None:
    focus = uuid4()
    neighbors = [uuid4(), uuid4(), uuid4()]
    pos = layout_nodes(focus, [focus, *neighbors])
    coords = {(p.x, p.y) for p in pos.values()}
    assert len(coords) == 4
    assert pos[focus].x == 0.0 and pos[focus].y == 0.0


def test_timeline_freshness_decay_events() -> None:
    claim_id = uuid4()
    claim = Claim(
        id=claim_id,
        public_slug="test-slug",
        canonical_claim_text="Test claim",
        normalized_claim_text="test claim",
        status=ClaimStatus.weak_evidence,
        confidence_score=0.5,
        controversy_score=0.1,
        evidence_score=0.3,
        freshness_score=0.7,
        evidence_count=1,
        discovery_score=0,
        created_at=datetime.now(tz=UTC) - timedelta(days=60),
        last_reviewed_at=datetime.now(tz=UTC) - timedelta(days=5),
    )
    ev = Evidence(
        id=uuid4(),
        claim_id=claim_id,
        source_type=EvidenceSourceType.manual_url,
        title="Old study",
        url="https://example.com",
        publisher="Press",
        stance=EvidenceStance.supports,
        credibility_score=0.6,
        retrieval_timestamp=datetime.now(tz=UTC) - timedelta(days=45),
        created_at=datetime.now(tz=UTC) - timedelta(days=45),
    )
    svc = ClaimTimelineService.__new__(ClaimTimelineService)
    events = svc._freshness_decay_events(claim, [ev])
    types = {e.event_type for e in events}
    assert "freshness_decay" in types
    assert any(e.title == "Freshness baseline" for e in events)


def test_safe_float_and_normalize_batch() -> None:
    assert safe_float(float("nan")) == 0.0
    assert normalize_batch([1.0, 1.0]) == [1.0, 1.0]
