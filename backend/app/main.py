"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.api.v1.routes import health, ops
from app.core.config import get_settings
from app.core.csrf import csrf_check_required, validate_csrf
from app.core.logging import configure_logging
from app.core.metrics import record_api_error, set_app_info
from app.core.rate_limit import limiter
from app.core.request_context import correlation_id_ctx
from app.core.telemetry import setup_telemetry
from app.services.ai.token_budget import TokenBudgetExceeded

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire Redis client into application state."""
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)
    set_app_info(version=settings.app_version, environment=settings.otel_environment)
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    app.state.redis = client
    logger.info("application_startup")
    yield
    await client.aclose()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Build FastAPI app with middleware and routes."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        """Propagate X-Request-ID."""
        cid = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        if cid:
            request.state.correlation_id = cid
        response = await call_next(request)
        if cid:
            response.headers["X-Request-ID"] = cid
        return response

    @app.middleware("http")
    async def csrf_protection(request: Request, call_next):
        """Double-submit CSRF for cookie-based browser sessions."""
        if csrf_check_required(request) and not validate_csrf(request, settings):
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": {
                        "code": "CSRF_VALIDATION_FAILED",
                        "message": "Missing or invalid CSRF token.",
                        "details": {},
                    },
                },
            )
        return await call_next(request)

    @app.exception_handler(TokenBudgetExceeded)
    async def openai_token_budget_handler(request: Request, exc: TokenBudgetExceeded):
        """OpenAI usage caps (development safety)."""
        record_api_error("OPENAI_TOKEN_BUDGET_EXCEEDED")
        logger.warning(
            "openai_token_budget_http",
            extra={"path": request.url.path, "detail": str(exc)},
        )
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": {
                    "code": "OPENAI_TOKEN_BUDGET_EXCEEDED",
                    "message": "OpenAI token budget exceeded for this request or day. "
                    "Raise limits or set OPENAI_ENFORCE_TOKEN_BUDGETS=false.",
                    "details": {
                        "kind": exc.kind,
                        "limit": exc.limit,
                        "used": exc.used,
                        "estimated": exc.estimated,
                    },
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        """Return safe JSON for unexpected errors."""
        record_api_error("INTERNAL_ERROR")
        logger.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "details": {},
                },
            },
        )

    app.include_router(health.router)
    app.include_router(ops.router)
    app.include_router(api_router)
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health", "/ready"],
    ).instrument(app)
    setup_telemetry(app, settings)
    return app


app = create_app()
