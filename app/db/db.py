"""Database setup for SQLite using async SQLAlchemy."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Base import is defined in models to avoid circular imports
from app.db.models import Base  # noqa: E402

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Create (or return) the global async engine."""
    global _engine

    if _engine is None:
        # Support templated path with mode: "data/bot_{mode}.db"
        raw_path = settings.database.db_path
        mode = getattr(settings.database, "mode", "default")
        resolved = raw_path.format(mode=mode) if "{mode}" in raw_path else raw_path

        db_path = Path(resolved)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        _engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=settings.database.echo_sql,
            future=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def init_db() -> None:
    """Initialize database (create tables)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a new async session (FastAPI dependency-friendly)."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def init_db_sync() -> None:
    """Synchronous helper for scripts."""
    asyncio.run(init_db())

