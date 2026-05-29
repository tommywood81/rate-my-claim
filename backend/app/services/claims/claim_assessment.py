"""Derive public claim scores and truth assessment from pending AI analyses."""

from __future__ import annotations

import json
from typing import Any, Literal

from app.core.enrichment_pipeline_config import TruthResolutionConfig, get_enrichment_pipeline_config

TruthLabel = Literal["supported", "refuted", "unclear"]

_TRUTH_VALUES = frozenset({"supported", "refuted", "unclear"})


def _parse_json_payload(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _coerce_unit_float(value: Any, default: float = 0.0) -> float:
    """Parse model score fields; tolerate categorical strings like low/medium/high."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return default
        qualitative = {
            "none": 0.0,
            "low": 0.25,
            "weak": 0.25,
            "poor": 0.2,
            "medium": 0.5,
            "moderate": 0.5,
            "fair": 0.45,
            "high": 0.75,
            "strong": 0.8,
            "good": 0.7,
        }
        if text in qualitative:
            return qualitative[text]
        try:
            return max(0.0, min(1.0, float(text)))
        except ValueError:
            return default
    return default


def assessment_confidence_score(data: dict[str, Any]) -> float:
    """
    Public confidence = how sure we are of the assessment (truth_label), not P(claim is true).

    Models often return truth_label refuted/supported with aggregate stuck at 0.5; align the
    displayed score when the verdict is definite but the numeric hedge remains at 0.5.
    """
    aggregate = _coerce_unit_float(data.get("aggregate"), 0.0)
    label = str(data.get("truth_label", "")).strip().lower()
    if label in ("supported", "refuted") and aggregate <= 0.55:
        return 0.82
    return aggregate


def scores_from_pending_analyses(analyses: list) -> tuple[float, float, float]:
    """Return (confidence, controversy, evidence_score) from the latest enrichment analyses."""
    from app.services.claims.assessment_provenance import latest_analyses_by_type

    confidence = 0.0
    controversy = 0.0
    evidence_score = 0.0

    for row in latest_analyses_by_type(analyses):
        if row.analysis_type == "confidence_analysis" and row.structured_payload:
            data = _parse_json_payload(row.structured_payload)
            scores_body = data.get("scores") if isinstance(data.get("scores"), dict) else data
            confidence = assessment_confidence_score(scores_body)
            evidence_score = _coerce_unit_float(
                scores_body.get("evidence_quality"),
                evidence_score,
            )
            hint = _coerce_unit_float(scores_body.get("controversy_hint"), 0.0)
            if hint > controversy:
                controversy = hint

        if row.analysis_type == "structured_verdict" and row.structured_payload:
            bundle = _parse_json_payload(row.structured_payload)
            verdict = bundle.get("verdict", {}) or {}
            if isinstance(verdict, dict):
                v_cont = float(verdict.get("controversy_hint", 0.0) or 0.0)
                v_conf = float(verdict.get("confidence_hint", 0.0) or 0.0)
                if v_cont > controversy:
                    controversy = v_cont
                if v_conf > 0 and confidence == 0:
                    confidence = v_conf

    return confidence, controversy, evidence_score


def has_corpus_evidence_from_analyses(analyses: list) -> bool:
    """True when enrichment attached library/URL lines to the assessment context."""
    from app.services.claims.assessment_provenance import (
        latest_analyses_by_type,
        parse_structured_payload,
    )

    for row in latest_analyses_by_type(analyses):
        if row.analysis_type not in {"confidence_analysis", "structured_verdict"}:
            continue
        data = parse_structured_payload(row.structured_payload)
        prov = data.get("provenance")
        if isinstance(prov, dict) and prov.get("has_corpus_evidence") is True:
            return True
    return False


def resolve_public_claim_scores(
    claim: object,
    *,
    pending_analyses: list | None = None,
) -> tuple[float, float, float]:
    """Merge stored claim scores with linked pending enrichment analyses when present."""
    confidence = float(getattr(claim, "confidence_score", 0) or 0)
    controversy = float(getattr(claim, "controversy_score", 0) or 0)
    evidence_score = float(getattr(claim, "evidence_score", 0) or 0)
    if not pending_analyses:
        return confidence, controversy, evidence_score
    has_confidence = any(row.analysis_type == "confidence_analysis" for row in pending_analyses)
    if not has_confidence:
        return confidence, controversy, evidence_score
    pc, pco, pev = scores_from_pending_analyses(pending_analyses)
    return pc, max(controversy, pco), max(evidence_score, pev)


def _in_narrow_band(value: float, low: float, high: float) -> bool:
    return low <= value <= high


def is_inconclusive_edge_case(
    *,
    aggregate: float,
    controversy: float,
    model_label: str | None,
    cfg: TruthResolutionConfig,
) -> bool:
    """
    True only for genuinely contested middling assessments (~1% target).

    Inconclusive when scores sit in a tight band, or controversy is high with middling aggregate.
    Model 'unclear' outside these bands is resolved to supported/refuted via thresholds.
    """
    narrow = _in_narrow_band(
        aggregate, cfg.inconclusive_aggregate_low, cfg.inconclusive_aggregate_high
    )
    contested = _in_narrow_band(
        aggregate, cfg.contested_aggregate_low, cfg.contested_aggregate_high
    )

    if model_label == "unclear" and narrow:
        return True

    if (
        controversy >= cfg.high_controversy_for_inconclusive
        and contested
        and model_label != "supported"
        and model_label != "refuted"
    ):
        return True

    if narrow and model_label not in ("supported", "refuted"):
        return True

    return False


def resolve_truth_label_from_scores(
    *,
    aggregate: float,
    controversy: float,
    model_label: str | None,
    cfg: TruthResolutionConfig | None = None,
) -> TruthLabel:
    """Map assessment scores to public supported / refuted / unclear."""
    rules = cfg or get_enrichment_pipeline_config().truth
    label = model_label if model_label in _TRUTH_VALUES else None

    if is_inconclusive_edge_case(
        aggregate=aggregate,
        controversy=controversy,
        model_label=label,
        cfg=rules,
    ):
        return "unclear"

    if label in ("supported", "refuted"):
        return label  # type: ignore[return-value]

    if label == "unclear":
        if aggregate >= rules.supported_aggregate_min:
            return "supported"
        if aggregate <= rules.refuted_aggregate_max:
            return "refuted"

    if aggregate >= rules.supported_aggregate_min:
        return "supported"
    if aggregate <= rules.refuted_aggregate_max:
        return "refuted"

    return "unclear"


def truth_label_from_analyses(
    analyses: list,
    *,
    processing_status: str | None,
    evidence_count: int | None = None,
    truth_cfg: TruthResolutionConfig | None = None,
) -> TruthLabel | None:
    """Truth banner label once automated enrichment has produced a verdict."""
    _ = evidence_count  # retained for API compatibility; corpus no longer gates truth
    if processing_status not in {
        "awaiting_moderation",
        "completed",
        "revision_requested",
    }:
        return None

    from app.services.claims.assessment_provenance import latest_analyses_by_type

    latest = latest_analyses_by_type(analyses)
    has_verdict = any(row.analysis_type == "structured_verdict" for row in latest)
    if not has_verdict:
        return None

    model_label: str | None = None
    aggregate = 0.5
    controversy = 0.0

    for row in latest:
        if row.analysis_type == "confidence_analysis" and row.structured_payload:
            data = _parse_json_payload(row.structured_payload)
            scores_body = data.get("scores") if isinstance(data.get("scores"), dict) else data
            aggregate = _coerce_unit_float(scores_body.get("aggregate"), aggregate)
            controversy = _coerce_unit_float(scores_body.get("controversy_hint"), controversy)
            raw = str(scores_body.get("truth_label", "")).strip().lower()
            if raw in _TRUTH_VALUES:
                model_label = raw

    _, controversy_from_verdict, _ = scores_from_pending_analyses(latest)
    controversy = max(controversy, controversy_from_verdict)

    return resolve_truth_label_from_scores(
        aggregate=aggregate,
        controversy=controversy,
        model_label=model_label,
        cfg=truth_cfg,
    )
