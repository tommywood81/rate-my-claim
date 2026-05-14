"""Password hashing and JWT helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings, get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    *,
    settings: Settings | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    cfg = settings or get_settings()
    expire = datetime.now(tz=UTC) + timedelta(minutes=cfg.access_token_expire_minutes)
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, cfg.secret_key, algorithm=cfg.algorithm)


def create_refresh_token(
    subject: str,
    jti: str,
    *,
    settings: Settings | None = None,
) -> str:
    """Create a signed JWT refresh token with a unique id for revocation."""
    cfg = settings or get_settings()
    expire = datetime.now(tz=UTC) + timedelta(days=cfg.refresh_token_expire_days)
    to_encode = {"sub": subject, "exp": expire, "type": "refresh", "jti": jti}
    return jwt.encode(to_encode, cfg.secret_key, algorithm=cfg.algorithm)


def decode_token(token: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and validate a JWT, raising JWTError on failure."""
    cfg = settings or get_settings()
    return jwt.decode(token, cfg.secret_key, algorithms=[cfg.algorithm])


def parse_uuid_subject(sub: str) -> UUID:
    """Parse JWT subject as UUID."""
    return UUID(sub)
