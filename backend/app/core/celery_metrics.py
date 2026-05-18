"""Collect Celery broker queue depth for Prometheus."""

from __future__ import annotations

import logging

import redis

from app.core.config import get_settings
from app.core.metrics import CELERY_QUEUE_DEPTH, CELERY_WORKERS

logger = logging.getLogger(__name__)


def refresh_celery_metrics() -> None:
    """Update gauges from Redis broker and Celery inspect (best-effort)."""
    settings = get_settings()
    try:
        client = redis.from_url(str(settings.celery_broker_url), decode_responses=True)
        for queue in ("celery",):
            try:
                depth = int(client.llen(queue))
            except redis.RedisError:
                depth = 0
            CELERY_QUEUE_DEPTH.labels(queue=queue).set(depth)
    except redis.RedisError as exc:
        logger.debug("celery_queue_metric_failed", extra={"error": str(exc)})
    finally:
        try:
            client.close()
        except Exception:
            pass

    try:
        from app.workers.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=1.0)
        ping = inspect.ping() if inspect else None
        CELERY_WORKERS.set(len(ping) if ping else 0)
    except Exception as exc:
        logger.debug("celery_worker_metric_failed", extra={"error": str(exc)})
        CELERY_WORKERS.set(0)
