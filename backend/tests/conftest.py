"""Shared pytest fixtures."""

from __future__ import annotations

import itertools

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.main import app

_client_ips = itertools.count(1)


@pytest.fixture(autouse=True)
async def dispose_sqlalchemy_engine() -> None:
    """Avoid asyncpg 'different loop' errors across pytest-asyncio tests."""
    yield
    await engine.dispose()


@pytest.fixture
async def async_client() -> AsyncClient:
    """HTTP client with FastAPI lifespan (Redis on app.state)."""
    host_octet = next(_client_ips) % 200 + 10
    client_addr = (f"10.0.0.{host_octet}", 12345)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, client=client_addr)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
