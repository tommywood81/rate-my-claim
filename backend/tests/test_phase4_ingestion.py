"""Phase 4: ingestion pipeline, duplicate detection, moderation state machine."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.claim import Claim, ClaimStatus, ProcessingStatus
from app.models.moderation import ModerationAction
from app.services.ingestion.claim_normalization import normalize_claim_text
from app.services.moderation.state_machine import (
    assert_claim_status_transition,
    assert_pending_transition,
)
from app.workers.tasks.enrichment_tasks import enrich_pending_claim_async
from tests.test_claim_ai_analysis_flow import StubAIProvider

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 with DATABASE_URL and Redis for Phase 4 tests"


def test_normalize_claim_text_collapses_whitespace() -> None:
    """Deterministic normalization is stable."""
    assert normalize_claim_text("  Hello   world.  ") == "Hello world."


def test_pending_transition_rules() -> None:
    """State machine allows spec transitions."""
    assert_pending_transition(
        ProcessingStatus.awaiting_moderation, ProcessingStatus.revision_requested
    )
    assert_pending_transition(ProcessingStatus.failed, ProcessingStatus.submitted)
    with pytest.raises(ValueError):
        assert_pending_transition(ProcessingStatus.submitted, ProcessingStatus.completed)


def test_claim_status_transition_rules() -> None:
    """Approved claim lifecycle transitions."""
    assert_claim_status_transition(ClaimStatus.weak_evidence, ClaimStatus.disputed)
    assert_claim_status_transition(ClaimStatus.disputed, ClaimStatus.weak_evidence)
    with pytest.raises(ValueError):
        assert_claim_status_transition(ClaimStatus.archived, ClaimStatus.disputed)


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_ingestion_pipeline_reaches_awaiting_moderation(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Submit → enrich (stub AI) → awaiting_moderation with embedding and audit."""
    monkeypatch.setattr(
        "app.workers.tasks.enrichment_tasks.get_ai_provider",
        lambda **kwargs: StubAIProvider(),
    )
    username = f"phase4_{os.getpid()}_{uuid4().hex[:6]}"
    password = "SeedDev!ChangeMe123"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    assert reg.status_code == 200, reg.text
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    csrf = login.cookies.get("rmc_csrf", "")

    submit = await async_client.post(
        "/api/v1/pending-claims",
        headers={"X-CSRF-Token": csrf} if csrf else {},
        json={
            "raw_claim_text": "Regular physical activity improves long-term cardiovascular outcomes.",
            "source_urls": [],
        },
    )
    assert submit.status_code == 200, submit.text
    pending_id = submit.json()["data"]["id"]

    await enrich_pending_claim_async(pending_id)

    status = await async_client.get(
        f"/api/v1/pending-claims/{pending_id}",
        headers={"X-CSRF-Token": csrf} if csrf else {},
    )
    assert status.status_code == 200
    data = status.json()["data"]
    assert data["processing_status"] == ProcessingStatus.awaiting_moderation.value
    assert data.get("canonical_candidate_text")

    async with AsyncSessionLocal() as session:
        from app.models.claim import PendingClaim

        from uuid import UUID as _UUID

        row = await session.get(PendingClaim, _UUID(str(pending_id)))
        assert row is not None
        assert row.embedding is not None
        assert row.normalized_claim_text

        audits = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.resource_id == row.id,
                    AuditLog.action.like("ingestion_%"),
                )
            )
        ).scalars().all()
        assert len(audits) >= 2


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_moderation_revision_and_claim_lifecycle(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Revision request, resubmit, approve; then dispute and restore approved claim."""
    stub = StubAIProvider()
    monkeypatch.setattr(
        "app.workers.tasks.enrichment_tasks.get_ai_provider",
        lambda **kwargs: stub,
    )
    monkeypatch.setattr(
        "app.services.moderation.moderation_service.get_ai_provider",
        lambda **kwargs: stub,
    )
    mod_password = os.environ.get("SEED_PASSWORD", "SeedDev!ChangeMe123")
    username = f"phase4_mod_{uuid4().hex[:6]}"
    password = "SeedDev!ChangeMe123"
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    user_login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    user_csrf = user_login.cookies.get("rmc_csrf", "")

    submit = await async_client.post(
        "/api/v1/pending-claims",
        headers={"X-CSRF-Token": user_csrf} if user_csrf else {},
        json={
            "raw_claim_text": "Vitamin D supplementation may reduce seasonal illness incidence in adults.",
            "source_urls": [],
        },
    )
    pending_id = submit.json()["data"]["id"]
    await enrich_pending_claim_async(pending_id)

    mod_login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "seed_moderator", "password": mod_password},
    )
    assert mod_login.status_code == 200
    mod_csrf = mod_login.cookies.get("rmc_csrf", "")

    rev = await async_client.post(
        "/api/v1/moderation/actions",
        headers={"X-CSRF-Token": mod_csrf} if mod_csrf else {},
        json={
            "action_type": "request_revision",
            "target_type": "pending_claim",
            "target_id": pending_id,
            "explanation": "Clarify population",
        },
    )
    assert rev.status_code == 200, rev.text

    user_login2 = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    user_csrf2 = user_login2.cookies.get("rmc_csrf", "")

    patch = await async_client.patch(
        f"/api/v1/pending-claims/{pending_id}",
        headers={"X-CSRF-Token": user_csrf2} if user_csrf2 else {},
        json={
            "raw_claim_text": "Vitamin D supplementation may reduce seasonal illness incidence in healthy adults.",
            "source_urls": [],
        },
    )
    assert patch.status_code == 200
    await enrich_pending_claim_async(pending_id)

    mod_login2 = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "seed_moderator", "password": mod_password},
    )
    mod_csrf2 = mod_login2.cookies.get("rmc_csrf", "")

    approve = await async_client.post(
        "/api/v1/moderation/actions",
        headers={"X-CSRF-Token": mod_csrf2} if mod_csrf2 else {},
        json={
            "action_type": "approve_claim",
            "target_type": "pending_claim",
            "target_id": pending_id,
            "explanation": "Approved after revision",
        },
    )
    assert approve.status_code == 200, approve.text
    claim_id = approve.json()["data"]["claim_id"]

    dispute = await async_client.post(
        "/api/v1/moderation/actions",
        headers={"X-CSRF-Token": mod_csrf2} if mod_csrf2 else {},
        json={
            "action_type": "dispute_claim",
            "target_type": "claim",
            "target_id": claim_id,
            "explanation": "New evidence surfaced",
        },
    )
    assert dispute.status_code == 200
    assert dispute.json()["data"]["status"] == ClaimStatus.disputed.value

    restore = await async_client.post(
        "/api/v1/moderation/actions",
        headers={"X-CSRF-Token": mod_csrf2} if mod_csrf2 else {},
        json={
            "action_type": "restore_claim",
            "target_type": "claim",
            "target_id": claim_id,
            "explanation": "Resolved dispute",
        },
    )
    assert restore.status_code == 200
    assert restore.json()["data"]["status"] == ClaimStatus.weak_evidence.value

    async with AsyncSessionLocal() as session:
        actions = (
            await session.execute(
                select(ModerationAction).where(ModerationAction.target_id == claim_id)
            )
        ).scalars().all()
        assert len(actions) >= 2
        claim = await session.get(Claim, claim_id)
        assert claim is not None
        assert str(claim.status) == ClaimStatus.weak_evidence.value
