"""Authentication routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_settings_dep
from app.core.config import Settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPairResponse, UserPublicResponse
from app.schemas.common import ErrorDetail, ErrorEnvelope, SuccessEnvelope
from app.services.auth.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access: str, refresh: str, settings: Settings) -> None:
    """Attach HTTP-only auth cookies."""
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


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    """Remove auth cookies."""
    response.delete_cookie(settings.access_cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(settings.refresh_cookie_name, path="/", domain=settings.cookie_domain)


@router.post("/register", response_model=SuccessEnvelope[UserPublicResponse])
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[UserPublicResponse]:
    """Create a new account."""
    svc = AuthService(db, settings)
    try:
        user = await svc.register(username=body.username, email=str(body.email), password=body.password)
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorEnvelope(
                error=ErrorDetail(code=code, message="Registration failed.", details={})
            ).model_dump(),
        ) from exc
    return SuccessEnvelope(data=UserPublicResponse.model_validate(user))


@router.post("/login", response_model=SuccessEnvelope[TokenPairResponse])
async def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SuccessEnvelope[TokenPairResponse]:
    """Issue JWT cookies and return tokens in body for API clients."""
    svc = AuthService(db, settings)
    try:
        user, access, refresh = await svc.login(username=body.username, password=body.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorEnvelope(
                error=ErrorDetail(code="invalid_credentials", message="Invalid credentials.", details={})
            ).model_dump(),
        ) from exc
    _set_auth_cookies(response, access, refresh, settings)
    return SuccessEnvelope(
        data=TokenPairResponse(access_token=access, refresh_token=refresh),
        meta={"user": UserPublicResponse.model_validate(user).model_dump()},
    )


@router.post("/refresh", response_model=SuccessEnvelope[TokenPairResponse])
async def refresh_session(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    refresh_cookie: Annotated[str | None, Cookie(alias="rmc_refresh")] = None,
) -> SuccessEnvelope[TokenPairResponse]:
    """Rotate refresh token (expects refresh cookie)."""
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_refresh")
    svc = AuthService(db, settings)
    try:
        user, access, refresh = await svc.refresh(refresh_token=refresh_cookie)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh") from exc
    _set_auth_cookies(response, access, refresh, settings)
    return SuccessEnvelope(
        data=TokenPairResponse(access_token=access, refresh_token=refresh),
        meta={"user": UserPublicResponse.model_validate(user).model_dump()},
    )


@router.post("/logout", response_model=SuccessEnvelope[dict])
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    refresh_token: Annotated[str | None, Cookie(alias="rmc_refresh")] = None,
) -> SuccessEnvelope[dict]:
    """Revoke refresh token and clear cookies."""
    svc = AuthService(db, settings)
    await svc.logout(refresh_token=refresh_token)
    _clear_auth_cookies(response, settings)
    return SuccessEnvelope(data={})


@router.get("/me", response_model=SuccessEnvelope[UserPublicResponse])
async def me(user: Annotated[User, Depends(get_current_user)]) -> SuccessEnvelope[UserPublicResponse]:
    """Return current user profile."""
    return SuccessEnvelope(data=UserPublicResponse.model_validate(user))
