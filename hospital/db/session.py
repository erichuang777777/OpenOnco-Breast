"""Async SQLAlchemy session factory + FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hospital.config import get_settings
from hospital.db.models import Base


def _make_engine():
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
    )


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False
        )
    return _session_factory


async def create_all_tables() -> None:
    """Create all tables (dev / test use; prod uses Alembic)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async session per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
