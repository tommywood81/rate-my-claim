"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import api_router
from app.api.v1.routes import health
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire Redis client into application state."""
    settings = get_settings()
    configure_logging(settings.log_level)
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

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        """Return safe JSON for unexpected errors."""
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
    app.include_router(api_router)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    return app


app = create_app()
