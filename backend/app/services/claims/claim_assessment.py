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


def scores_from_pending_analyses(analyses: list) -> tuple[float, float, float]:
    """Return (confidence, controversy, evidence_score) from enrichment analyses."""
    confidence = 0.0
    controversy = 0.0
    evidence_score = 0.0

    for row in analyses:
        if row.analysis_type == "confidence_analysis" and row.structured_payload:
            data = _parse_json_payload(row.structured_payload)
            confidence = float(data.get("aggregate", confidence) or confidence)
            evidence_score = float(data.get("evidence_quality", evidence_score) or evidence_score)
            hint = float(data.get("controversy_hint", 0.0) or 0.0)
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


def truth_label_from_analyses(
    analyses: list,
    *,
    processing_status: str | None,
) -> TruthLabel | None:
    """Truth banner label once automated enrichment has produced a verdict."""
    if processing_status not in {
        "awaiting_moderation",
        "completed",
        "revision_requested",
    }:
        return None

    has_verdict = any(row.analysis_type == "structured_verdict" for row in analyses)
    if not has_verdict:
        return None

    label: str | None = None
    aggregate = 0.0

    for row in analyses:
        if row.analysis_type == "confidence_analysis" and row.structured_payload:
            data = _parse_json_payload(row.structured_payload)
            aggregate = float(data.get("aggregate", aggregate) or aggregate)
            raw = str(data.get("truth_label", "")).strip().lower()
            if raw in _TRUTH_VALUES:
                label = raw

    if label in _TRUTH_VALUES:
        return label  # type: ignore[return-value]

    # Fallback when model omits truth_label (older rows).
    if aggregate >= 0.62:
        return "supported"
    if aggregate <= 0.38:
        return "refuted"
    return "unclear"
