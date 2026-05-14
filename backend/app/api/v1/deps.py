"""FastAPI dependencies for DB, auth, and RBAC."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_token, parse_uuid_subject
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.users_repository import UserRepository

security = HTTPBearer(auto_error=False)


def _coerce_role(value: str) -> UserRole:
    """Map stored role string to enum."""
    return UserRole(value)


async def get_settings_dep() -> Settings:
    """Inject settings."""
    return get_settings()


async def get_optional_token(
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    access_cookie: Annotated[str | None, Cookie(alias="rmc_access")] = None,
) -> str | None:
    """Resolve bearer token or access cookie."""
    if authorization and authorization.scheme.lower() == "bearer":
        return authorization.credentials
    return access_cookie


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(get_optional_token)],
) -> User:
    """Require authenticated user."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
        user_id = parse_uuid_subject(str(payload["sub"]))
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_missing")
    return user


def require_roles(*roles: UserRole):
    """Factory enforcing RBAC."""

    allowed = set(roles)

    async def _inner(user: Annotated[User, Depends(get_current_user)]) -> User:
        """Raise if user role not allowed."""
        ur = _coerce_role(str(user.role))
        if ur == UserRole.admin:
            return user
        if ur not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _inner


ModeratorUser = Annotated[User, Depends(require_roles(UserRole.moderator, UserRole.admin))]
