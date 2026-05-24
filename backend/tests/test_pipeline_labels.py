"""Tests for public pipeline visibility labels."""

from app.models.claim import ProcessingStatus
from app.services.claims.pipeline_labels import assessment_complete, visibility_label


def test_assessment_complete_for_completed_and_legacy_awaiting() -> None:
    assert assessment_complete(ProcessingStatus.completed.value) is True
    assert assessment_complete(ProcessingStatus.awaiting_moderation.value) is True
    assert assessment_complete(ProcessingStatus.enriching.value) is False


def test_visibility_label_processing_and_live() -> None:
    assert visibility_label(processing_status="enriching", claim_status="weak_evidence") == "Checking…"
    assert visibility_label(processing_status="completed", claim_status="weak_evidence") == "Live"
    assert (
        visibility_label(processing_status="completed", claim_status="weak_evidence", evidence_count=2)
        == "Live · sourced"
    )
    assert visibility_label(processing_status="failed", claim_status="weak_evidence") == "Check interrupted"
