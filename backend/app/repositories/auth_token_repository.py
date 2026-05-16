"""One-time auth token persistence."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models.auth_token import AuthOneTimeToken, AuthTokenPurpose
from app.repositories.base import RepositoryBase


def hash_auth_token(raw: str) -> str:
    """Return stable SHA-256 hex digest for storage."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuthTokenRepository(RepositoryBase):
    """Create and consume password-reset / email-verify tokens."""

    async def create_token(
        self,
        *,
        user_id: UUID,
        purpose: AuthTokenPurpose,
        expires_at: datetime,
    ) -> tuple[AuthOneTimeToken, str]:
        """Insert hashed token; return row and raw secret (show once to user)."""
        raw = secrets.token_urlsafe(32)
        row = AuthOneTimeToken(
            user_id=user_id,
            token_hash=hash_auth_token(raw),
            purpose=purpose.value,
            expires_at=expires_at,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row, raw

    async def consume_valid_token(
        self,
        *,
        raw_token: str,
        purpose: AuthTokenPurpose,
    ) -> AuthOneTimeToken | None:
        """Mark token used if valid; return None if missing/expired/used."""
        digest = hash_auth_token(raw_token)
        stmt = select(AuthOneTimeToken).where(
            AuthOneTimeToken.token_hash == digest,
            AuthOneTimeToken.purpose == purpose.value,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None or row.used_at is not None or row.expires_at < datetime.now(tz=UTC):
            return None
        row.used_at = datetime.now(tz=UTC)
        await self._session.flush()
        return row
