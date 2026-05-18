"""Operational endpoints (metrics enrichment)."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.celery_metrics import refresh_celery_metrics
from app.core.metrics import APP_INFO

router = APIRouter(tags=["ops"])


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape endpoint with Celery queue gauges refreshed each scrape."""
    refresh_celery_metrics()
    body = generate_latest()
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
