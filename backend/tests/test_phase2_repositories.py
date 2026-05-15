"""Phase 2: repository wiring and base class."""

from __future__ import annotations

from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import RepositoryBase
from app.repositories.claims_repository import ClaimRepository, HybridSearchRepository


def test_repository_base_stores_session() -> None:
    """RepositoryBase keeps a reference to the async session."""
    mock = MagicMock(spec=AsyncSession)
    repo = RepositoryBase(mock)
    assert repo._session is mock


def test_claim_repository_inherits_base() -> None:
    """ClaimRepository subclasses RepositoryBase."""
    mock = MagicMock(spec=AsyncSession)
    repo = ClaimRepository(mock)
    assert isinstance(repo, RepositoryBase)


def test_hybrid_search_repository_inherits_base() -> None:
    """HybridSearchRepository subclasses RepositoryBase."""
    mock = MagicMock(spec=AsyncSession)
    repo = HybridSearchRepository(mock)
    assert isinstance(repo, RepositoryBase)
