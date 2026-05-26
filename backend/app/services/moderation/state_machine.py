"""Valid moderation transitions for pending pipeline and approved claims."""

from __future__ import annotations

from app.models.claim import ClaimStatus, ProcessingStatus

# Pending claim processing_status transitions (moderator / system)
PENDING_MODERATOR_ACTIONS: dict[ProcessingStatus, frozenset[ProcessingStatus]] = {
    ProcessingStatus.awaiting_moderation: frozenset(
        {
            ProcessingStatus.completed,
            ProcessingStatus.rejected,
            ProcessingStatus.revision_requested,
        }
    ),
    ProcessingStatus.revision_requested: frozenset(
        {
            ProcessingStatus.rejected,
            ProcessingStatus.submitted,
        }
    ),
    # Auto-assessment finishes at completed; staff may still send back for edits.
    ProcessingStatus.completed: frozenset(
        {
            ProcessingStatus.revision_requested,
            ProcessingStatus.rejected,
        }
    ),
    ProcessingStatus.failed: frozenset({ProcessingStatus.submitted}),
}

# Approved claim status transitions (moderator)
CLAIM_STATUS_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    ClaimStatus.verified: frozenset({ClaimStatus.disputed, ClaimStatus.archived}),
    ClaimStatus.weak_evidence: frozenset({ClaimStatus.disputed, ClaimStatus.archived}),
    ClaimStatus.insufficient_evidence: frozenset(
        {ClaimStatus.disputed, ClaimStatus.archived}
    ),
    ClaimStatus.outdated: frozenset({ClaimStatus.disputed, ClaimStatus.archived}),
    ClaimStatus.disputed: frozenset(
        {ClaimStatus.verified, ClaimStatus.weak_evidence, ClaimStatus.insufficient_evidence}
    ),
    ClaimStatus.archived: frozenset(
        {ClaimStatus.verified, ClaimStatus.weak_evidence, ClaimStatus.insufficient_evidence}
    ),
}


def _coerce_processing_status(value: ProcessingStatus | str) -> ProcessingStatus:
    if isinstance(value, ProcessingStatus):
        return value
    return ProcessingStatus(str(value))


def assert_pending_transition(current: ProcessingStatus | str, target: ProcessingStatus | str) -> None:
    """Raise ValueError if moderator cannot move pending to target status."""
    cur = _coerce_processing_status(current)
    tgt = _coerce_processing_status(target)
    allowed = PENDING_MODERATOR_ACTIONS.get(cur, frozenset())
    if tgt not in allowed:
        raise ValueError("invalid_pending_transition")


def _coerce_claim_status(value: ClaimStatus | str) -> ClaimStatus:
    if isinstance(value, ClaimStatus):
        return value
    return ClaimStatus(str(value))


def assert_claim_status_transition(current: ClaimStatus | str, target: ClaimStatus | str) -> None:
    """Raise ValueError if moderator cannot change claim status."""
    try:
        cur = _coerce_claim_status(current)
        tgt = _coerce_claim_status(target)
    except ValueError as exc:
        raise ValueError("invalid_claim_status") from exc
    allowed = CLAIM_STATUS_TRANSITIONS.get(cur, frozenset())
    if tgt not in allowed:
        raise ValueError("invalid_claim_transition")
