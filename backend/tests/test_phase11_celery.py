"""Phase 11: Celery task wiring and enrichment idempotency."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.workers.celery_app import celery_app, process_pending_claim
from app.workers.tasks.enrichment_tasks import enrich_pending_claim_async, run_pending_enrichment

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 for Redis lock integration test"


def test_celery_registers_process_pending_task() -> None:
    assert celery_app.tasks.get("claims.process_pending") is not None


def test_run_pending_enrichment_invalid_uuid_does_not_raise() -> None:
    """Sync entrypoint should swallow missing pending rows."""
    run_pending_enrichment(str(uuid4()))


@pytest.mark.asyncio
async def test_enrich_missing_pending_is_no_op() -> None:
    await enrich_pending_claim_async(uuid4())


@pytest.mark.asyncio
async def test_enrich_skips_when_lock_not_acquired() -> None:
    with patch(
        "app.workers.tasks.enrichment_tasks.enrichment_task_lock",
    ) as lock_mock:
        lock_mock.return_value.__aenter__ = AsyncMock(return_value=False)
        lock_mock.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch(
            "app.workers.tasks.enrichment_tasks._run_pipeline",
            new_callable=AsyncMock,
        ) as pipeline:
            await enrich_pending_claim_async(uuid4())
            pipeline.assert_not_called()


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_enrichment_lock_prevents_double_acquire() -> None:
    from app.services.ai.idempotency import enrichment_task_lock

    pid = uuid4()
    async with enrichment_task_lock(pid) as first:
        assert first is True
        async with enrichment_task_lock(pid) as second:
            assert second is False


def test_process_pending_claim_retries_on_failure() -> None:
    task = process_pending_claim
    assert task.max_retries == 3
