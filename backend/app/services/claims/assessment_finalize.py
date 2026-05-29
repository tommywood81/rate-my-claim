"""Finalize pending enrichment onto the live claim (no human approval gate)."""



from __future__ import annotations



import json

import logging

from datetime import UTC, datetime

from uuid import UUID



from sqlalchemy.ext.asyncio import AsyncSession



from app.models.claim import Claim, ClaimRevision, ClaimStatus, PendingClaim, ProcessingStatus

from app.models.evidence import Evidence, EvidenceSourceType, EvidenceStance

from app.repositories.ai_analysis_repository import AIAnalysisRepository

from app.repositories.claims_repository import ClaimRepository

from app.services.ai.factory import get_ai_provider

from app.services.claims.assessment_provenance import (

    assessment_run_source,

    attach_provenance_to_payload,

    count_evidence_for_run,

    count_non_finalize_evidence,

    extraction_metadata_for_block,

    latest_analyses_by_type,

    parse_structured_payload,

    pending_analysis_ids_on_claim,

)

from app.services.claims.claim_assessment import scores_from_pending_analyses

from app.services.claims.live_claim_sync import sync_pending_to_linked_claim



logger = logging.getLogger(__name__)



_IMPORT_TYPES = frozenset({"structured_verdict", "confidence_analysis"})





async def _append_assessment_evidence(

    session: AsyncSession,

    *,

    claim: Claim,

    line_map: dict[int, dict],

    pending: PendingClaim,

    provider,

    run_source: str,

) -> int:

    """Append archive/URL context lines used during enrichment (never delete prior runs)."""

    added = 0

    now = datetime.now(tz=UTC)

    for _line_no, block in sorted(line_map.items()):

        kind = str(block.get("kind") or "")

        meta = extraction_metadata_for_block(block, assessment_run_source=run_source)

        if kind == "url":

            title = str(block.get("title") or block.get("url") or "Source")

            url = str(block.get("url") or "") or None

            excerpt = str(block.get("text") or "")[:8000]

            credibility = float(block.get("credibility_score", 0.5) or 0.5)

            retrieved_raw = block.get("retrieved_at")

            retrieved_at = now

            if retrieved_raw:

                try:

                    parsed = datetime.fromisoformat(str(retrieved_raw).replace("Z", "+00:00"))

                    retrieved_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

                except ValueError:

                    retrieved_at = now

            pub_raw = block.get("publication_date")

            publication_date = None

            if pub_raw:

                try:

                    publication_date = datetime.fromisoformat(str(pub_raw).replace("Z", "+00:00"))

                    if publication_date.tzinfo is None:

                        publication_date = publication_date.replace(tzinfo=UTC)

                except ValueError:

                    publication_date = None

            source_type = (

                EvidenceSourceType.api.value

                if block.get("source_channel") == "reputable_web"

                else EvidenceSourceType.user_submission.value

            )

            ev = Evidence(

                claim_id=claim.id,

                source_type=source_type,

                title=title[:512],

                url=url,

                publisher=str(block.get("publisher") or "")[:255] or None,

                summary=excerpt[:4000] if excerpt else None,

                cleaned_content=excerpt or None,

                publication_date=publication_date,

                stance=EvidenceStance.contextualizes.value,

                credibility_score=credibility,

                retrieval_timestamp=retrieved_at,

                retrieval_source=run_source,

                extraction_metadata=meta,

                created_by=pending.submitted_by,

            )

            session.add(ev)

            if excerpt:

                text_for_emb = f"{title}\n{excerpt}"[:8000]

                vec, emb_model = await provider.generate_embedding(text_for_emb)

                ev.embedding = vec

                ev.embedding_model = emb_model

                ev.embedding_version = pending.embedding_version

            added += 1

            continue

        if kind == "db_evidence":

            title = str(block.get("title") or "Archive match")

            excerpt = str(block.get("excerpt") or "")[:8000]

            ev = Evidence(

                claim_id=claim.id,

                source_type=EvidenceSourceType.api.value,

                title=title[:512],

                url=None,

                summary=excerpt[:4000] if excerpt else None,

                cleaned_content=excerpt or None,

                stance=EvidenceStance.contextualizes.value,

                credibility_score=0.45,

                retrieval_timestamp=now,

                retrieval_source=run_source,

                extraction_metadata=meta,

                created_by=pending.submitted_by,

            )

            session.add(ev)

            added += 1

    await session.flush()

    return added





def _line_map_from_analyses(analyses) -> dict[int, dict]:

    for row in latest_analyses_by_type(analyses):

        if row.analysis_type != "structured_verdict" or not row.structured_payload:

            continue

        bundle = parse_structured_payload(row.structured_payload)

        raw = bundle.get("line_map") or (bundle.get("provenance") or {}).get("line_map") or {}

        out: dict[int, dict] = {}

        for key, value in raw.items():

            try:

                out[int(key)] = value  # type: ignore[assignment]

            except (TypeError, ValueError):

                continue

        if out:

            return out

    return {}





async def _import_pending_analyses_to_claim(

    ai_repo: AIAnalysisRepository,

    *,

    claim: Claim,

    pending_analyses: list,

    created_by_job: str,

) -> int:

    """Copy pending assessment rows onto the claim (append-only; skip already-imported ids)."""

    claim_rows = await ai_repo.list_for_target("claim", claim.id)

    already = pending_analysis_ids_on_claim(claim_rows)

    imported = 0

    for row in pending_analyses:

        if row.analysis_type not in _IMPORT_TYPES:

            continue

        if str(row.id) in already:

            continue

        payload = parse_structured_payload(row.structured_payload)

        payload = attach_provenance_to_payload(

            payload,

            pending_analysis_id=row.id,

            provenance=payload.get("provenance") or {},

        )

        await ai_repo.add_analysis(

            target_type="claim",

            target_id=claim.id,

            model_name=row.model_name,

            provider=row.provider,

            analysis_type=row.analysis_type,

            generated_text=row.generated_text,

            structured_payload=payload,

            confidence=row.confidence,

            created_by_job=created_by_job,

        )

        imported += 1

    return imported





async def finalize_pending_assessment(

    session: AsyncSession,

    pending_id: UUID,

    *,

    actor_id: UUID | None = None,

    created_by_job: str = "enrichment",

    explanation: str | None = None,

) -> Claim | None:

    """Promote enrichment output to the linked live claim and mark assessment complete."""

    repo = ClaimRepository(session)

    ai_repo = AIAnalysisRepository(session)

    pending = await repo.get_pending(pending_id)

    if pending is None or pending.linked_claim_id is None:

        return None



    claim = await repo.get_claim_by_id(pending.linked_claim_id)

    if claim is None or claim.deleted_at is not None:

        return None



    analyses = await ai_repo.list_for_target("pending_claim", pending_id)

    canonical = pending.canonical_candidate_text or pending.raw_claim_text

    prev_canonical = claim.canonical_claim_text

    confidence, controversy, evidence_quality = scores_from_pending_analyses(analyses)

    if analyses:

        claim.confidence_score = confidence

        claim.controversy_score = controversy

        claim.evidence_score = evidence_quality



    claim.canonical_claim_text = canonical

    claim.normalized_claim_text = pending.normalized_claim_text or canonical

    if pending.embedding is not None:

        claim.embedding = pending.embedding

        claim.embedding_model = pending.embedding_model

        claim.embedding_version = pending.embedding_version

        claim.embedding_at = pending.embedding_at



    run_at = datetime.now(tz=UTC)

    run_source = assessment_run_source(run_at)

    line_map = _line_map_from_analyses(analyses)

    provider = get_ai_provider(budget_scope=f"finalize:{pending_id}")

    await _append_assessment_evidence(

        session,

        claim=claim,

        line_map=line_map,

        pending=pending,

        provider=provider,

        run_source=run_source,

    )

    run_count = await count_evidence_for_run(session, claim.id, run_source)

    non_finalize = await count_non_finalize_evidence(session, claim.id)

    claim.evidence_count = non_finalize + run_count

    if run_count > 0:

        citation_score = min(1.0, 0.15 + 0.12 * run_count)

        claim.evidence_score = max(float(claim.evidence_score or 0.0), citation_score)

        if claim.status == ClaimStatus.insufficient_evidence.value:

            claim.status = ClaimStatus.weak_evidence.value

    elif analyses and claim.status == ClaimStatus.insufficient_evidence.value:

        claim.status = ClaimStatus.weak_evidence.value



    claim.last_reviewed_at = run_at

    pending.processing_status = ProcessingStatus.completed



    if prev_canonical.strip() != canonical.strip():

        session.add(

            ClaimRevision(

                claim_id=claim.id,

                previous_status=None,

                new_status=str(claim.status),

                previous_confidence=None,

                new_confidence=claim.confidence_score,

                explanation=f"Canonical claim text updated during assessment ({created_by_job}).",

                created_by=actor_id,

                created_at=run_at,

            )

        )



    session.add(

        ClaimRevision(

            claim_id=claim.id,

            previous_status=None,

            new_status=str(claim.status),

            previous_confidence=None,

            new_confidence=claim.confidence_score,

            explanation=explanation or "Automated assessment published to live claim.",

            created_by=actor_id,

            created_at=run_at,

        )

    )



    await _import_pending_analyses_to_claim(

        ai_repo,

        claim=claim,

        pending_analyses=analyses,

        created_by_job=created_by_job,

    )



    await sync_pending_to_linked_claim(session, pending_id)

    await session.flush()

    logger.info(

        "assessment_finalized",

        extra={

            "claim_id": str(claim.id),

            "pending_id": str(pending_id),

            "evidence_run_count": run_count,

            "run_source": run_source,

            "job": created_by_job,

        },

    )

    return claim


