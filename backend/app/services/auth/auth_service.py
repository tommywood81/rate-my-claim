"""Authentication use-cases."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    parse_uuid_subject,
    verify_password,
)
from app.models.auth_token import AuthTokenPurpose
from app.models.user import User, UserRole
from app.repositories.auth_token_repository import AuthTokenRepository
from app.repositories.users_repository import UserRepository
from app.services.auth.request_context import AuthRequestContext
from app.services.auth.session_audit import SessionAudit


class AuthService:
    """Register, login, refresh, logout, reset, and verification flows."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        """Attach session and optional settings override."""
        self._session = session
        self._settings = settings or get_settings()
        self._users = UserRepository(session)
        self._tokens = AuthTokenRepository(session)
        self._audit = SessionAudit(session)

    async def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        ctx: AuthRequestContext,
    ) -> tuple[User, str | None]:
        """Create a new account; optionally return email-verify token for dev."""
        if await self._users.get_by_username(username):
            raise ValueError("username_taken")
        if await self._users.get_by_email(email):
            raise ValueError("email_taken")
        role = UserRole.user
        user_count = await self._session.scalar(select(func.count()).select_from(User))
        if (user_count or 0) == 0:
            role = UserRole.admin
        user = await self._users.create_user(
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            role=role,
        )
        await self._audit.log(
            action="auth_register",
            ctx=ctx,
            actor_id=user.id,
            resource_id=user.id,
            details={"username": username, "role": user.role},
        )
        verify_raw = await self._issue_email_verify_token(user.id)
        return user, verify_raw

    async def login(
        self,
        *,
        username: str,
        password: str,
        ctx: AuthRequestContext,
    ) -> tuple[User, str, str]:
        """Validate credentials and return user plus token pair."""
        user = await self._users.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            await self._audit.log(
                action="auth_login_failed",
                ctx=ctx,
                details={"username": username},
            )
            raise ValueError("invalid_credentials")
        user, access, refresh = await self._issue_session(user)
        await self._audit.log(
            action="auth_login_success",
            ctx=ctx,
            actor_id=user.id,
            resource_id=user.id,
        )
        return user, access, refresh

    async def refresh(self, *, refresh_token: str, ctx: AuthRequestContext) -> tuple[User, str, str]:
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
        user, access, refresh = await self._issue_session(user)
        await self._audit.log(
            action="auth_refresh",
            ctx=ctx,
            actor_id=user.id,
            resource_id=user.id,
            details={"rotated_from_jti": jti[:8]},
        )
        return user, access, refresh

    async def logout(self, *, refresh_token: str | None, ctx: AuthRequestContext, user_id: UUID | None) -> None:
        """Revoke refresh token if present."""
        jti = None
        if refresh_token:
            try:
                payload = decode_token(refresh_token)
                jti = str(payload.get("jti", ""))
                await self._users.revoke_refresh_token(jti)
            except Exception:
                pass
        await self._audit.log(
            action="auth_logout",
            ctx=ctx,
            actor_id=user_id,
            resource_id=user_id,
            details={"jti_prefix": jti[:8] if jti else None},
        )

    async def request_password_reset(
        self,
        *,
        email: str,
        ctx: AuthRequestContext,
    ) -> str | None:
        """Create reset token if user exists; return raw token for dev exposure only."""
        user = await self._users.get_by_email(email)
        if user is None:
            return None
        expires = datetime.now(tz=UTC) + timedelta(
            minutes=self._settings.auth_password_reset_expire_minutes
        )
        _, raw = await self._tokens.create_token(
            user_id=user.id,
            purpose=AuthTokenPurpose.password_reset,
            expires_at=expires,
        )
        await self._audit.log(
            action="auth_password_reset_requested",
            ctx=ctx,
            actor_id=user.id,
            resource_id=user.id,
        )
        return raw

    async def reset_password(self, *, raw_token: str, new_password: str, ctx: AuthRequestContext) -> None:
        """Consume reset token and set new password."""
        row = await self._tokens.consume_valid_token(
            raw_token=raw_token,
            purpose=AuthTokenPurpose.password_reset,
        )
        if row is None:
            raise ValueError("invalid_or_expired_token")
        await self._users.update_password(row.user_id, get_password_hash(new_password))
        await self._audit.log(
            action="auth_password_reset_completed",
            ctx=ctx,
            actor_id=row.user_id,
            resource_id=row.user_id,
        )

    async def request_email_verification(
        self,
        *,
        user_id: UUID,
        ctx: AuthRequestContext,
    ) -> str | None:
        """Issue a new email verification token."""
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise ValueError("user_not_found")
        if user.email_verified_at is not None:
            raise ValueError("already_verified")
        raw = await self._issue_email_verify_token(user_id)
        await self._audit.log(
            action="auth_email_verify_requested",
            ctx=ctx,
            actor_id=user_id,
            resource_id=user_id,
        )
        return raw

    async def verify_email(self, *, raw_token: str, ctx: AuthRequestContext) -> User:
        """Mark email verified using one-time token."""
        row = await self._tokens.consume_valid_token(
            raw_token=raw_token,
            purpose=AuthTokenPurpose.email_verify,
        )
        if row is None:
            raise ValueError("invalid_or_expired_token")
        await self._users.set_email_verified(row.user_id)
        user = await self._users.get_by_id(row.user_id)
        if user is None:
            raise ValueError("user_not_found")
        await self._audit.log(
            action="auth_email_verified",
            ctx=ctx,
            actor_id=user.id,
            resource_id=user.id,
        )
        return user

    async def _issue_session(self, user: User) -> tuple[User, str, str]:
        jti = secrets.token_urlsafe(32)
        expires = datetime.now(tz=UTC) + timedelta(days=self._settings.refresh_token_expire_days)
        await self._users.add_refresh_token(user_id=user.id, jti=jti, expires_at=expires)
        access = create_access_token(str(user.id), settings=self._settings)
        refresh = create_refresh_token(str(user.id), jti, settings=self._settings)
        return user, access, refresh

    async def _issue_email_verify_token(self, user_id: UUID) -> str | None:
        user = await self._users.get_by_id(user_id)
        if user is None or user.email_verified_at is not None:
            return None
        expires = datetime.now(tz=UTC) + timedelta(hours=self._settings.auth_email_verify_expire_hours)
        _, raw = await self._tokens.create_token(
            user_id=user_id,
            purpose=AuthTokenPurpose.email_verify,
            expires_at=expires,
        )
        return raw
