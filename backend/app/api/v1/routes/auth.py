"""Authentication routes."""

from __future__ import annotations

from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from jose import JWTError
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_optional_token, get_settings_dep
from app.core.brute_force import BruteForceGuard
from app.core.config import Settings, get_settings
from app.core.csrf import clear_csrf_cookie, generate_csrf_token, set_csrf_cookie
from app.core.rate_limit import limiter
from app.core.security import decode_token, parse_uuid_subject
from app.db.session import get_db
from app.models.user import User
from app.repositories.users_repository import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPairResponse,
    UserPublicResponse,
    VerifyEmailRequest,
)
from app.schemas.common import ErrorDetail, ErrorEnvelope, SuccessEnvelope
from app.services.auth.auth_service import AuthService
from app.services.auth.request_context import auth_context_from_request

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()


def _redis(request: Request) -> redis.Redis:
    return request.app.state.redis


def _set_auth_cookies(response: Response, access: str, refresh: str, settings: Settings) -> str:
    """Attach HTTP-only auth cookies and CSRF cookie; return CSRF token."""
    response.set_cookie(
        key=settings.access_cookie_name,
        value=access,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
        domain=settings.cookie_domain,
    )
    csrf = generate_csrf_token()
    set_csrf_cookie(response, csrf, settings)
    return csrf


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    """Remove auth and CSRF cookies."""
    response.delete_cookie(settings.access_cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(settings.refresh_cookie_name, path="/", domain=settings.cookie_domain)
    clear_csrf_cookie(response, settings)


def _dev_meta(settings: Settings, **extra: str) -> dict:
    if settings.auth_expose_dev_tokens or settings.debug:
        return extra
    return {}


async def _optional_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(get_optional_token)],
) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = parse_uuid_subject(str(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        return None
    return await UserRepository(db).get_by_id(user_id)


@router.post("/register", response_model=SuccessEnvelope[UserPublicResponse])
@limiter.limit(_settings.auth_register_rate_limit)
async def register(
    request: Request,
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[UserPublicResponse]:
    """Create a new account."""
    ctx = auth_context_from_request(request)
    svc = AuthService(db, settings)
    try:
        user, verify_raw = await svc.register(
            username=body.username,
            email=str(body.email),
            password=body.password,
            ctx=ctx,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=code, message="Registration failed.", details={})
            ).model_dump(),
        ) from exc
    meta = _dev_meta(settings, email_verify_token=verify_raw or "")
    return SuccessEnvelope(data=UserPublicResponse.model_validate(user), meta=meta)


@router.post("/login", response_model=SuccessEnvelope[TokenPairResponse])
@limiter.limit(_settings.auth_login_rate_limit)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[TokenPairResponse]:
    """Issue JWT cookies and return tokens in body for API clients."""
    ctx = auth_context_from_request(request)
    account_key = f"{body.username}:{ctx.ip_address or get_remote_address(request)}"
    guard = BruteForceGuard(_redis(request), settings)
    if await guard.is_locked(account_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="account_locked",
                    message="Too many failed login attempts. Try again later.",
                    details={},
                )
            ).model_dump(),
        )

    svc = AuthService(db, settings)
    try:
        user, access, refresh = await svc.login(username=body.username, password=body.password, ctx=ctx)
        await guard.clear_failures(account_key)
    except ValueError as exc:
        if str(exc) == "invalid_credentials":
            await guard.record_failure(account_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="invalid_credentials", message="Invalid credentials.", details={})
            ).model_dump(),
        ) from exc
    csrf = _set_auth_cookies(response, access, refresh, settings)
    return SuccessEnvelope(
        data=TokenPairResponse(access_token=access, refresh_token=refresh),
        meta={
            "user": UserPublicResponse.model_validate(user).model_dump(),
            "csrf_token": csrf,
        },
    )


@router.post("/refresh", response_model=SuccessEnvelope[TokenPairResponse])
async def refresh_session(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    refresh_cookie: Annotated[str | None, Cookie(alias="rmc_refresh")] = None,
) -> SuccessEnvelope[TokenPairResponse]:
    """Rotate refresh token (expects refresh cookie)."""
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_refresh")
    ctx = auth_context_from_request(request)
    svc = AuthService(db, settings)
    try:
        user, access, refresh = await svc.refresh(refresh_token=refresh_cookie, ctx=ctx)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh") from exc
    csrf = _set_auth_cookies(response, access, refresh, settings)
    return SuccessEnvelope(
        data=TokenPairResponse(access_token=access, refresh_token=refresh),
        meta={
            "user": UserPublicResponse.model_validate(user).model_dump(),
            "csrf_token": csrf,
        },
    )


@router.post("/logout", response_model=SuccessEnvelope[dict])
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    user: Annotated[User | None, Depends(_optional_user)],
    refresh_token: Annotated[str | None, Cookie(alias="rmc_refresh")] = None,
) -> SuccessEnvelope[dict]:
    """Revoke refresh token and clear cookies."""
    ctx = auth_context_from_request(request)
    svc = AuthService(db, settings)
    await svc.logout(refresh_token=refresh_token, ctx=ctx, user_id=user.id if user else None)
    _clear_auth_cookies(response, settings)
    return SuccessEnvelope(data={})


@router.get("/me", response_model=SuccessEnvelope[UserPublicResponse])
async def me(user: Annotated[User, Depends(get_current_user)]) -> SuccessEnvelope[UserPublicResponse]:
    """Return current user profile."""
    return SuccessEnvelope(data=UserPublicResponse.model_validate(user))


@router.post("/forgot-password", response_model=SuccessEnvelope[MessageResponse])
@limiter.limit(_settings.auth_forgot_password_rate_limit)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[MessageResponse]:
    """Request password reset email (token returned in dev meta only)."""
    ctx = auth_context_from_request(request)
    svc = AuthService(db, settings)
    raw = await svc.request_password_reset(email=str(body.email), ctx=ctx)
    return SuccessEnvelope(
        data=MessageResponse(message="If an account exists, reset instructions were sent."),
        meta=_dev_meta(settings, password_reset_token=raw or ""),
    )


@router.post("/reset-password", response_model=SuccessEnvelope[MessageResponse])
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[MessageResponse]:
    """Set a new password using a valid reset token."""
    ctx = auth_context_from_request(request)
    svc = AuthService(db, settings)
    try:
        await svc.reset_password(raw_token=body.token, new_password=body.new_password, ctx=ctx)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="invalid_or_expired_token",
                    message="Reset link is invalid or expired.",
                    details={},
                )
            ).model_dump(),
        ) from exc
    return SuccessEnvelope(data=MessageResponse(message="Password updated."))


@router.post("/verify-email/request", response_model=SuccessEnvelope[MessageResponse])
async def request_verify_email(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[MessageResponse]:
    """Resend email verification for the current user."""
    ctx = auth_context_from_request(request)
    svc = AuthService(db, settings)
    try:
        raw = await svc.request_email_verification(user_id=user.id, ctx=ctx)
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=code, message="Verification not sent.", details={})
            ).model_dump(),
        ) from exc
    return SuccessEnvelope(
        data=MessageResponse(message="Verification email sent."),
        meta=_dev_meta(settings, email_verify_token=raw or ""),
    )


@router.post("/verify-email", response_model=SuccessEnvelope[UserPublicResponse])
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[UserPublicResponse]:
    """Confirm email with one-time token."""
    ctx = auth_context_from_request(request)
    svc = AuthService(db, settings)
    try:
        user = await svc.verify_email(raw_token=body.token, ctx=ctx)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorEnvelope(
                error=ErrorDetail(
                    code="invalid_or_expired_token",
                    message="Verification link is invalid or expired.",
                    details={},
                )
            ).model_dump(),
        ) from exc
    return SuccessEnvelope(data=UserPublicResponse.model_validate(user))
