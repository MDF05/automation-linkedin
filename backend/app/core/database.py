"""
Async SQLAlchemy engine dan session factory.

Gunakan `get_db` sebagai FastAPI dependency untuk mendapatkan
AsyncSession yang sudah di-manage (commit/rollback/close otomatis).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import AsyncGenerator as AsyncGeneratorType

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

# ------------------------------------------------------------------ #
# Engine
# ------------------------------------------------------------------ #
_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    # Pool settings yang cocok untuk workload single-user bot
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # validasi koneksi sebelum digunakan (reconnect otomatis)
    echo=False,           # set True untuk debug SQL query
)

# ------------------------------------------------------------------ #
# Session factory
# ------------------------------------------------------------------ #
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # objek tetap accessible setelah commit
    autoflush=False,
    autocommit=False,
)


# ------------------------------------------------------------------ #
# FastAPI dependency
# ------------------------------------------------------------------ #
async def get_db() -> AsyncGeneratorType[AsyncSession, None]:
    """
    FastAPI dependency yang menyediakan AsyncSession per-request.

    Penggunaan::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
