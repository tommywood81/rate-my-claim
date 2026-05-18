"""OpenTelemetry tracing (optional; enabled via OTEL_ENABLED)."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger(__name__)


def setup_telemetry(app: FastAPI, settings: Settings) -> None:
    """Configure OTLP tracing and auto-instrumentation when enabled."""
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("otel_packages_missing", extra={"error": str(exc)})
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.otel_environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/health,/ready")
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument(enable_commenter=True)

    logger.info(
        "otel_tracing_enabled",
        extra={
            "endpoint": settings.otel_exporter_endpoint,
            "service": settings.otel_service_name,
        },
    )
