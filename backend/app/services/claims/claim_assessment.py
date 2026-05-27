"""Derive public claim scores and truth assessment from pending AI analyses."""

from __future__ import annotations

import json
from typing import Any, Literal

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


def assessment_confidence_score(data: dict[str, Any]) -> float:
    """
    Public confidence = how sure we are of the assessment (truth_label), not P(claim is true).

    Models often return truth_label refuted/supported with aggregate stuck at 0.5; align the
    displayed score when the verdict is definite but the numeric hedge remains at 0.5.
    """
    aggregate = float(data.get("aggregate", 0) or 0)
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
            evidence_score = float(
                scores_body.get("evidence_quality", evidence_score) or evidence_score
            )
            hint = float(scores_body.get("controversy_hint", 0.0) or 0.0)
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


def truth_label_from_analyses(
    analyses: list,
    *,
    processing_status: str | None,
    evidence_count: int | None = None,
) -> TruthLabel | None:
    """Truth banner label once automated enrichment has produced a verdict."""
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

    label: str | None = None
    aggregate = 0.0

    for row in latest:
        if row.analysis_type == "confidence_analysis" and row.structured_payload:
            data = _parse_json_payload(row.structured_payload)
            scores_body = data.get("scores") if isinstance(data.get("scores"), dict) else data
            aggregate = float(scores_body.get("aggregate", aggregate) or aggregate)
            raw = str(scores_body.get("truth_label", "")).strip().lower()
            if raw in _TRUTH_VALUES:
                label = raw

    has_corpus = has_corpus_evidence_from_analyses(analyses)
    if not has_corpus and evidence_count is not None and evidence_count > 0:
        has_corpus = True

    if label in _TRUTH_VALUES:
        if not has_corpus and label in ("supported", "refuted"):
            return "unclear"
        return label  # type: ignore[return-value]

    # Fallback when model omits truth_label (older rows).
    if not has_corpus:
        return "unclear"
    if aggregate >= 0.62:
        return "supported"
    if aggregate <= 0.38:
        return "refuted"
    return "unclear"
