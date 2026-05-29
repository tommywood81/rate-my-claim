"""Public truth label resolution (supported / refuted / inconclusive edge cases)."""

from __future__ import annotations

from app.core.enrichment_pipeline_config import TruthResolutionConfig
from app.services.claims.claim_assessment import (
    is_inconclusive_edge_case,
    resolve_truth_label_from_scores,
    truth_label_from_analyses,
)

_CFG = TruthResolutionConfig()


def test_supported_without_corpus_when_model_says_supported() -> None:
    class Row:
        def __init__(self, analysis_type: str, payload: dict) -> None:
            self.analysis_type = analysis_type
            self.structured_payload = payload

    analyses = [
        Row(
            "confidence_analysis",
            {
                "scores": {
                    "aggregate": 0.9,
                    "truth_label": "supported",
                    "controversy_hint": 0.05,
                },
                "provenance": {"has_corpus_evidence": False},
            },
        ),
        Row("structured_verdict", {"verdict": {"verdict_summary": "Supported."}}),
    ]
    assert truth_label_from_analyses(analyses, processing_status="completed") == "supported"


def test_refuted_high_aggregate_without_corpus() -> None:
    assert (
        resolve_truth_label_from_scores(
            aggregate=0.88,
            controversy=0.1,
            model_label="refuted",
            cfg=_CFG,
        )
        == "refuted"
    )


def test_narrow_band_stays_inconclusive() -> None:
    assert (
        resolve_truth_label_from_scores(
            aggregate=0.50,
            controversy=0.2,
            model_label="unclear",
            cfg=_CFG,
        )
        == "unclear"
    )
    assert is_inconclusive_edge_case(
        aggregate=0.50,
        controversy=0.2,
        model_label="unclear",
        cfg=_CFG,
    )


def test_model_unclear_high_confidence_resolves_supported() -> None:
    assert (
        resolve_truth_label_from_scores(
            aggregate=0.85,
            controversy=0.1,
            model_label="unclear",
            cfg=_CFG,
        )
        == "supported"
    )


def test_scores_from_analyses_tolerates_low_evidence_quality_string() -> None:
    from app.services.claims.claim_assessment import scores_from_pending_analyses

    class Row:
        def __init__(self, analysis_type: str, payload: dict) -> None:
            self.analysis_type = analysis_type
            self.structured_payload = payload

    analyses = [
        Row(
            "confidence_analysis",
            {
                "scores": {
                    "aggregate": 0.85,
                    "evidence_quality": "low",
                    "controversy_hint": 0.1,
                    "truth_label": "supported",
                }
            },
        ),
        Row("structured_verdict", {"verdict": {"verdict_summary": "ok"}}),
    ]
    conf, cont, ev = scores_from_pending_analyses(analyses)
    assert conf >= 0.8
    assert ev == 0.25
    assert cont == 0.1


def test_high_controversy_contested_band_inconclusive() -> None:
    assert (
        resolve_truth_label_from_scores(
            aggregate=0.50,
            controversy=0.80,
            model_label=None,
            cfg=_CFG,
        )
        == "unclear"
    )
