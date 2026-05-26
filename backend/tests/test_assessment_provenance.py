"""Assessment audit trail helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.claims.assessment_provenance import (
    assessment_run_source,
    filter_evidence_for_public_display,
    is_assessment_finalize_source,
    latest_analyses_by_type,
    latest_assessment_run_source,
    pending_analysis_ids_on_claim,
)


class _Ev:
    def __init__(self, retrieval_source: str | None) -> None:
        self.retrieval_source = retrieval_source


def test_assessment_run_source_is_sortable() -> None:
    a = assessment_run_source(datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC))
    b = assessment_run_source(datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC))
    assert a < b
    assert a.startswith("assessment_finalize:")


def test_legacy_finalize_source_detected() -> None:
    assert is_assessment_finalize_source("assessment_finalize")
    assert is_assessment_finalize_source("assessment_finalize:20260520T120000Z")
    assert not is_assessment_finalize_source("manual_url")


def test_filter_evidence_keeps_latest_run_only() -> None:
    old = _Ev("assessment_finalize:20260519T120000Z")
    new = _Ev("assessment_finalize:20260520T120000Z")
    other = _Ev("moderator")
    out = filter_evidence_for_public_display([old, new, other])
    assert len(out) == 2
    assert new in out
    assert other in out
    assert old not in out


def test_latest_assessment_run_source() -> None:
    tags = [
        "assessment_finalize:20260519T120000Z",
        "assessment_finalize:20260520T120000Z",
        None,
    ]
    assert latest_assessment_run_source(tags) == "assessment_finalize:20260520T120000Z"


def test_latest_analyses_by_type() -> None:
    class Row:
        def __init__(self, t: str) -> None:
            self.analysis_type = t

    rows = [Row("structured_verdict"), Row("confidence_analysis"), Row("structured_verdict")]
    out = latest_analyses_by_type(rows)
    assert [r.analysis_type for r in out] == ["structured_verdict", "confidence_analysis"]


def test_pending_analysis_ids_on_claim() -> None:
    class Row:
        structured_payload = '{"provenance": {"pending_analysis_id": "abc-123"}}'

    assert pending_analysis_ids_on_claim([Row()]) == {"abc-123"}
