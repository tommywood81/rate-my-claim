"""Tests for on-demand claim AI moderation guards."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services.claims.claim_ai_moderation import (
    analyses_use_stub_provider,
    claim_has_attached_evidence,
    on_demand_analysis_available,
    on_demand_analysis_block_reason,
)
from app.services.moderation.state_machine import assert_pending_transition
from app.models.claim import ProcessingStatus
import pytest


def _analysis(*, provider: str = "openai") -> SimpleNamespace:
    return SimpleNamespace(
        provider=provider,
        created_at=datetime.now(tz=UTC),
    )


def _claim(*, evidence_count: int = 0, evidence_items: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        evidence_count=evidence_count,
        evidence_items=evidence_items or [],
    )


def test_claim_has_attached_evidence_from_count_or_items() -> None:
    assert claim_has_attached_evidence(_claim(evidence_count=1)) is True
    assert claim_has_attached_evidence(_claim(evidence_items=[object()])) is True
    assert claim_has_attached_evidence(_claim()) is False


def test_on_demand_analysis_blocked_without_evidence() -> None:
    claim = _claim()
    analyses = [_analysis()]
    assert on_demand_analysis_block_reason(claim=claim, analyses=analyses) == "no_evidence"
    assert on_demand_analysis_available(claim=claim, analyses=analyses) is False


def test_on_demand_analysis_blocked_for_stub_provider() -> None:
    claim = _claim(evidence_count=2)
    analyses = [_analysis(provider="stub")]
    assert on_demand_analysis_block_reason(claim=claim, analyses=analyses) == "stub_provider"
    assert analyses_use_stub_provider(analyses) is True


def test_on_demand_analysis_allowed_with_evidence_and_live_provider() -> None:
    claim = _claim(evidence_count=1)
    analyses = [_analysis(provider="openai")]
    assert on_demand_analysis_block_reason(claim=claim, analyses=analyses) is None
    assert on_demand_analysis_available(claim=claim, analyses=analyses) is True


def test_reprocess_disallowed_from_awaiting_moderation() -> None:
    with pytest.raises(ValueError):
        assert_pending_transition(ProcessingStatus.awaiting_moderation, ProcessingStatus.submitted)
