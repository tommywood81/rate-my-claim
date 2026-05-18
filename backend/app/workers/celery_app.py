"""Celery application instance."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rate_my_claim",
    broker=str(settings.celery_broker_url),
    backend=str(settings.celery_result_backend),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="claims.process_pending", bind=True, max_retries=3)
def process_pending_claim(self, pending_id: str) -> None:
    """Idempotent background enrichment for a pending claim."""
    from app.workers.tasks.enrichment_tasks import run_pending_enrichment

    try:
        run_pending_enrichment(pending_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30) from exc


@celery_app.task(name="evidence.process_ingestion_job")
def process_ingestion_job(job_id: str) -> None:
    """Process one URL ingestion job into an evidence artifact."""
    from app.workers.tasks.evidence_tasks import run_process_ingestion_job

    run_process_ingestion_job(job_id)


@celery_app.task(name="evidence.poll_rss_feeds")
def poll_rss_feeds() -> int:
    """Poll curated RSS feeds and ingest new articles."""
    from app.workers.tasks.evidence_tasks import run_poll_rss_feeds

    return run_poll_rss_feeds()