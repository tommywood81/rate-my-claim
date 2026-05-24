"""User-facing pipeline labels mapped from processing_status (interpretation layer)."""

from __future__ import annotations

from app.models.claim import ProcessingStatus

_PIPELINE_STAGES: list[tuple[frozenset[ProcessingStatus], str, str]] = [
    (
        frozenset({ProcessingStatus.submitted}),
        "received",
        "Received",
    ),
    (
        frozenset(
            {
                ProcessingStatus.embedding,
                ProcessingStatus.duplicate_check,
                ProcessingStatus.canonicalizing,
            }
        ),
        "analyzing",
        "Analyzing",
    ),
    (
        frozenset({ProcessingStatus.enriching}),
        "gathering_evidence",
        "Gathering evidence",
    ),
    (
        frozenset({ProcessingStatus.awaiting_moderation, ProcessingStatus.completed}),
        "assessed",
        "Assessment complete",
    ),
    (
        frozenset({ProcessingStatus.revision_requested}),
        "revised",
        "Revision requested",
    ),
    (
        frozenset({ProcessingStatus.failed}),
        "failed",
        "Check interrupted",
    ),
    (
        frozenset({ProcessingStatus.rejected}),
        "rejected",
        "Withdrawn",
    ),
]

_ORDER = [
    "received",
    "analyzing",
    "gathering_evidence",
    "assessed",
]


def pipeline_stage_key(status: str | ProcessingStatus | None) -> str | None:
    """Stable stage id for UI stepper."""
    if status is None:
        return None
    try:
        proc = ProcessingStatus(str(status))
    except ValueError:
        return None
    for statuses, key, _ in _PIPELINE_STAGES:
        if proc in statuses:
            return key
    return None


def pipeline_stage_label(status: str | ProcessingStatus | None) -> str | None:
    """Human-readable current pipeline label."""
    if status is None:
        return None
    try:
        proc = ProcessingStatus(str(status))
    except ValueError:
        return None
    for statuses, _, label in _PIPELINE_STAGES:
        if proc in statuses:
            return label
    return None


def pipeline_stage_index(stage_key: str | None) -> int:
    """Index for progress UI (-1 if unknown)."""
    if stage_key is None:
        return -1
    try:
        return _ORDER.index(stage_key)
    except ValueError:
        return -1


def assessment_complete(processing_status: str | None) -> bool:
    """True when automated assessment has finished and the claim is fully live."""
    proc = str(processing_status or "")
    return proc in {
        ProcessingStatus.completed.value,
        ProcessingStatus.awaiting_moderation.value,
    }


def visibility_label(
    *,
    processing_status: str | None,
    claim_status: str,
    evidence_count: int = 0,
) -> str:
    """Browse/list badge: checking vs live (no human review tiers)."""
    proc = str(processing_status or "")
    if proc in {
        ProcessingStatus.submitted.value,
        ProcessingStatus.embedding.value,
        ProcessingStatus.duplicate_check.value,
        ProcessingStatus.canonicalizing.value,
        ProcessingStatus.enriching.value,
    }:
        return "Checking…"
    if proc == ProcessingStatus.failed.value:
        return "Check interrupted"
    if proc == ProcessingStatus.rejected.value:
        return "Withdrawn"
    if proc == ProcessingStatus.revision_requested.value:
        return "Revision requested"
    if assessment_complete(proc):
        if evidence_count >= 2:
            return "Live · sourced"
        return "Live"
    return "Live"
