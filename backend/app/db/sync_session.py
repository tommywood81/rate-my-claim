"""Synchronous engine and session for Celery workers and Alembic."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=sync_engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Context manager yielding a sync session with commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
