"""Shared repository foundation for async SQLAlchemy sessions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class RepositoryBase:
    """Attach a request- or script-scoped async session to concrete repositories."""

    def __init__(self, session: AsyncSession) -> None:
        """Store the active database session."""
        self._session = session
