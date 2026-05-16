"""Phase 3: auth flows, RBAC, refresh rotation, CSRF (opt-in integration)."""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 with DATABASE_URL and Redis for Phase 3 auth tests"


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_refresh_token_rotation(async_client: AsyncClient) -> None:
    """Using refresh once invalidates the old jti."""
    password = os.environ.get("SEED_PASSWORD", "SeedDev!ChangeMe123")
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "seed_moderator", "password": password},
    )
    assert login.status_code == 200, login.text
    refresh_a = login.cookies.get("rmc_refresh")
    assert refresh_a

    rot = await async_client.post("/api/v1/auth/refresh")
    assert rot.status_code == 200, rot.text
    refresh_b = rot.cookies.get("rmc_refresh")
    assert refresh_b and refresh_b != refresh_a

    stale = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"rmc_refresh": refresh_a},
    )
    assert stale.status_code == 401


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_rbac_moderation_forbidden_for_regular_user(async_client: AsyncClient) -> None:
    """Non-moderator cannot access moderation queue."""
    username = f"phase3_user_{os.getpid()}"
    password = "SeedDev!ChangeMe123"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"phase3_{os.getpid()}@example.com",
            "password": password,
        },
    )
    assert reg.status_code == 200, reg.text
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text

    mod = await async_client.get("/api/v1/moderation/pending-claims")
    assert mod.status_code == 403


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_expert_summary_requires_expert_role(async_client: AsyncClient) -> None:
    """Regular user cannot access expert summary."""
    username = f"phase3_exp_{os.getpid()}"
    password = "SeedDev!ChangeMe123"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"phase3_exp_{os.getpid()}@example.com",
            "password": password,
        },
    )
    assert reg.status_code == 200
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    expert = await async_client.get("/api/v1/expert/summary")
    assert expert.status_code == 403


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_password_reset_flow_with_dev_token(async_client: AsyncClient) -> None:
    """Forgot + reset password using token from dev meta."""
    os.environ["AUTH_EXPOSE_DEV_TOKENS"] = "true"
    from app.core.config import get_settings

    get_settings.cache_clear()
    username = f"phase3_reset_{os.getpid()}"
    email = f"phase3_reset_{os.getpid()}@example.com"
    password = "SeedDev!ChangeMe123"
    new_password = "SeedDev!ChangeMe456"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert reg.status_code == 200, reg.text

    forgot = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    assert forgot.status_code == 200, forgot.text
    token = (forgot.json().get("meta") or {}).get("password_reset_token")
    assert token

    reset = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert reset.status_code == 200, reset.text

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": new_password},
    )
    assert login.status_code == 200, login.text

    forgot2 = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    token2 = (forgot2.json().get("meta") or {}).get("password_reset_token")
    assert token2
    restore = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token2, "new_password": password},
    )
    assert restore.status_code == 200, restore.text


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_csrf_required_for_cookie_logout(async_client: AsyncClient) -> None:
    """Cookie session POST without CSRF header is rejected."""
    password = os.environ.get("SEED_PASSWORD", "SeedDev!ChangeMe123")
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "seed_moderator", "password": password},
    )
    assert login.status_code == 200
    blocked = await async_client.post("/api/v1/auth/logout")
    assert blocked.status_code == 403
    csrf = login.cookies.get("rmc_csrf", "")
    ok = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert ok.status_code == 200
