"""Authentication use-cases."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    parse_uuid_subject,
    verify_password,
)
from app.models.user import User, UserRole
from app.repositories.users_repository import UserRepository


class AuthService:
    """Register, login, refresh, and logout flows."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """Attach session and optional settings override."""
        self._session = session
        self._settings = settings or get_settings()
        self._users = UserRepository(session)

    async def register(self, *, username: str, email: str, password: str) -> User:
        """Create a new user account."""
        if await self._users.get_by_username(username):
            raise ValueError("username_taken")
        if await self._users.get_by_email(email):
            raise ValueError("email_taken")
        role = UserRole.user

        user_count = await self._session.scalar(select(func.count()).select_from(User))
        if (user_count or 0) == 0:
            role = UserRole.admin
        return await self._users.create_user(
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            role=role,
        )

    async def login(self, *, username: str, password: str) -> tuple[User, str, str]:
        """Validate credentials and return user plus token pair."""
        user = await self._users.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("invalid_credentials")
        jti = secrets.token_urlsafe(32)
        expires = datetime.now(tz=UTC) + timedelta(days=self._settings.refresh_token_expire_days)
        await self._users.add_refresh_token(user_id=user.id, jti=jti, expires_at=expires)
        access = create_access_token(str(user.id), settings=self._settings)
        refresh = create_refresh_token(str(user.id), jti, settings=self._settings)
        return user, access, refresh

    async def refresh(self, *, refresh_token: str) -> tuple[User, str, str]:
        """Rotate refresh token and issue new access token."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("invalid_refresh")
        jti = str(payload["jti"])
        row = await self._users.get_refresh_token(jti)
        if row is None or row.revoked_at is not None or row.expires_at < datetime.now(tz=UTC):
            raise ValueError("invalid_refresh")
        user = await self._users.get_by_id(parse_uuid_subject(str(payload["sub"])))
        if user is None:
            raise ValueError("invalid_refresh")
        await self._users.revoke_refresh_token(jti)
        new_jti = secrets.token_urlsafe(32)
        expires = datetime.now(tz=UTC) + timedelta(days=self._settings.refresh_token_expire_days)
        await self._users.add_refresh_token(user_id=user.id, jti=new_jti, expires_at=expires)
        access = create_access_token(str(user.id), settings=self._settings)
        refresh = create_refresh_token(str(user.id), new_jti, settings=self._settings)
        return user, access, refresh

    async def logout(self, *, refresh_token: str | None) -> None:
        """Revoke refresh token if present."""
        if not refresh_token:
            return
        try:
            payload = decode_token(refresh_token)
            jti = str(payload.get("jti", ""))
            await self._users.revoke_refresh_token(jti)
        except Exception:
            return
