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
        frozenset({ProcessingStatus.awaiting_moderation}),
        "ai_complete",
        "Complete (AI)",
    ),
    (
        frozenset({ProcessingStatus.completed}),
        "moderated",
        "Moderated",
    ),
    (
        frozenset({ProcessingStatus.revision_requested}),
        "revised",
        "Revision requested",
    ),
    (
        frozenset({ProcessingStatus.failed}),
        "failed",
        "Analysis interrupted",
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
    "ai_complete",
    "moderated",
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


def visibility_label(
    *,
    processing_status: str | None,
    claim_status: str,
    moderation_reviewed: bool,
) -> str:
    """Browse/list badge: processing vs live unverified vs live verified."""
    proc = str(processing_status or "")
    if proc in {
        ProcessingStatus.submitted.value,
        ProcessingStatus.embedding.value,
        ProcessingStatus.duplicate_check.value,
        ProcessingStatus.canonicalizing.value,
        ProcessingStatus.enriching.value,
        ProcessingStatus.failed.value,
    }:
        return "Processing"
    if proc == ProcessingStatus.rejected.value:
        return "Withdrawn"
    if moderation_reviewed or proc == ProcessingStatus.completed.value:
        if claim_status == "verified":
            return "Live (verified)"
        return "Live (reviewed)"
    if proc == ProcessingStatus.revision_requested.value:
        return "Revision requested"
    return "Live (unverified)"
