"""User persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken, User, UserRole


class UserRepository:
    """Async user lookups and creation."""

    def __init__(self, session: AsyncSession) -> None:
        """Attach session."""
        self._session = session

    async def get_by_username(self, username: str) -> User | None:
        """Find user by unique username."""
        stmt = select(User).where(User.username == username)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Find user by email."""
        stmt = select(User).where(User.email == email)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Load user by id."""
        stmt = select(User).where(User.id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_user(
        self, *, username: str, email: str, password_hash: str, role: UserRole = UserRole.user
    ) -> User:
        """Persist a new user."""
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role.value,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def add_refresh_token(self, *, user_id: UUID, jti: str, expires_at: datetime) -> RefreshToken:
        """Persist a refresh token row."""
        row = RefreshToken(user_id=user_id, jti=jti, expires_at=expires_at, created_at=datetime.now(tz=UTC))
        self._session.add(row)
        await self._session.flush()
        return row

    async def revoke_refresh_token(self, jti: str) -> None:
        """Mark refresh token revoked."""
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row and row.revoked_at is None:
            row.revoked_at = datetime.now(tz=UTC)

    async def get_refresh_token(self, jti: str) -> RefreshToken | None:
        """Load refresh token by jti."""
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        return (await self._session.execute(stmt)).scalar_one_or_none()
