"""Assessment audit trail helpers (append-only analyses, run-tagged evidence)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import ClaimRevision, PendingClaim
from app.models.evidence import Evidence
from app.models.moderation import ModerationAction

_ASSESSMENT_SOURCE_PREFIX = "assessment_finalize:"
_LEGACY_ASSESSMENT_SOURCE = "assessment_finalize"


def assessment_run_source(run_at: datetime | None = None) -> str:
    """Tag evidence rows from a single finalize pass (sortable, unique per second)."""
    ts = run_at or datetime.now(tz=UTC)
    return f"{_ASSESSMENT_SOURCE_PREFIX}{ts.strftime('%Y%m%dT%H%M%SZ')}"


def is_assessment_finalize_source(retrieval_source: str | None) -> bool:
    """True when evidence was attached during automated/staff finalize."""
    if not retrieval_source:
        return False
    return (
        retrieval_source == _LEGACY_ASSESSMENT_SOURCE
        or retrieval_source.startswith(_ASSESSMENT_SOURCE_PREFIX)
    )


def latest_assessment_run_source(sources: list[str | None]) -> str | None:
    """Newest assessment_finalize tag among evidence retrieval_source values."""
    tags = [s for s in sources if s and is_assessment_finalize_source(s)]
    return max(tags) if tags else None


def filter_evidence_for_public_display(items: list) -> list:
    """
    Show non-finalize evidence plus only the latest assessment run's attached sources.

    Older assessment_finalize:* rows remain in the DB for audit but are hidden on the public page.
    """
    finalize = [ev for ev in items if is_assessment_finalize_source(getattr(ev, "retrieval_source", None))]
    if not finalize:
        return list(items)
    latest = latest_assessment_run_source([getattr(ev, "retrieval_source", None) for ev in finalize])
    if not latest:
        return list(items)
    out: list = []
    for ev in items:
        src = getattr(ev, "retrieval_source", None)
        if is_assessment_finalize_source(src) and src != latest:
            continue
        out.append(ev)
    return out


def latest_analyses_by_type(analyses: list) -> list:
    """Keep the newest row per analysis_type (input should be newest-first)."""
    seen: set[str] = set()
    out: list = []
    for row in analyses:
        t = str(row.analysis_type)
        if t in seen:
            continue
        seen.add(t)
        out.append(row)
    return out


def parse_structured_payload(raw: str | dict | None) -> dict:
    """Decode AI analysis JSON payload."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def pending_analysis_ids_on_claim(analyses: list) -> set[str]:
    """Pending analysis UUIDs already copied onto this claim."""
    ids: set[str] = set()
    for row in analyses:
        data = parse_structured_payload(row.structured_payload)
        prov = data.get("provenance") or {}
        pid = prov.get("pending_analysis_id")
        if pid:
            ids.add(str(pid))
    return ids


def build_enrichment_provenance(
    *,
    pending: PendingClaim,
    canonical_claim_text: str,
    line_map: dict,
    embedding_model: str | None,
    embedding_version: str | None,
    has_corpus_evidence: bool,
    url_artifact_ids: list[str],
    borrowed_evidence_ids: list[str],
    reputable_source_urls: list[str] | None = None,
    assessment_run_at: datetime | None = None,
) -> dict:
    """Snapshot inputs stored inside structured_payload for later audit."""
    run_at = assessment_run_at or datetime.now(tz=UTC)
    return {
        "assessment_run_at": run_at.isoformat(),
        "assessment_run_source": assessment_run_source(run_at),
        "raw_claim_text": (pending.raw_claim_text or "")[:8000],
        "canonical_claim_text": canonical_claim_text[:8000],
        "normalized_claim_text": (pending.normalized_claim_text or "")[:8000],
        "embedding_model": embedding_model,
        "embedding_version": embedding_version,
        "has_corpus_evidence": has_corpus_evidence,
        "url_artifact_ids": url_artifact_ids,
        "borrowed_evidence_ids": borrowed_evidence_ids,
        "reputable_source_urls": reputable_source_urls or [],
        "line_map": line_map,
    }


def attach_provenance_to_payload(
    payload: dict | None,
    *,
    pending_analysis_id: UUID,
    provenance: dict,
) -> dict:
    """Merge audit fields into an analysis payload before persistence."""
    out = dict(payload or {})
    out["provenance"] = {**provenance, "pending_analysis_id": str(pending_analysis_id)}
    return out


def extraction_metadata_for_block(block: dict, *, assessment_run_source: str) -> str:
    """JSON lineage for evidence rows (stable source references)."""
    meta = {
        "assessment_run_source": assessment_run_source,
        "kind": block.get("kind"),
    }
    if block.get("evidence_id"):
        meta["source_evidence_id"] = block["evidence_id"]
    if block.get("artifact_id"):
        meta["artifact_id"] = block["artifact_id"]
    if block.get("url"):
        meta["url"] = block["url"]
    return json.dumps(meta)


async def claim_has_staff_activity(
    session: AsyncSession,
    *,
    claim_id: UUID,
    pending_id: UUID | None,
) -> bool:
    """
    True when staff (moderator/admin) took an explicit action on this claim or its pending row.

    Automated enrichment does not set this; most claims remain AI-assessed only.
    """
    targets: list[tuple[str, UUID]] = [("claim", claim_id)]
    if pending_id is not None:
        targets.append(("pending_claim", pending_id))

    for target_type, target_id in targets:
        stmt = (
            select(ModerationAction.id)
            .where(
                ModerationAction.target_type == target_type,
                ModerationAction.target_id == target_id,
                ModerationAction.actor_id.is_not(None),
            )
            .limit(1)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is not None:
            return True

    rev_stmt = (
        select(ClaimRevision.id)
        .where(
            ClaimRevision.claim_id == claim_id,
            ClaimRevision.created_by.is_not(None),
        )
        .limit(1)
    )
    return (await session.execute(rev_stmt)).scalar_one_or_none() is not None


async def count_evidence_for_run(session: AsyncSession, claim_id: UUID, run_source: str) -> int:
    """Evidence rows attached during a specific assessment finalize pass."""
    stmt = select(func.count()).select_from(Evidence).where(
        Evidence.claim_id == claim_id,
        Evidence.retrieval_source == run_source,
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def count_non_finalize_evidence(session: AsyncSession, claim_id: UUID) -> int:
    """Evidence not tied to an assessment_finalize run (moderator-added, legacy, etc.)."""
    stmt = (
        select(func.count())
        .select_from(Evidence)
        .where(
            Evidence.claim_id == claim_id,
            or_(
                Evidence.retrieval_source.is_(None),
                ~Evidence.retrieval_source.startswith(_ASSESSMENT_SOURCE_PREFIX),
            ),
        )
    )
    return int((await session.execute(stmt)).scalar_one() or 0)
