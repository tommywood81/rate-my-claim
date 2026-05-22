"""Aggregate v1 API routes."""

from fastapi import APIRouter

from app.api.v1.routes import atlas, auth, claims, evidence, expert, graph, moderation, search, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(atlas.router)
api_router.include_router(claims.router)
api_router.include_router(graph.router)
api_router.include_router(evidence.router)
api_router.include_router(moderation.router)
api_router.include_router(search.router)
api_router.include_router(users.router)
api_router.include_router(expert.router)
