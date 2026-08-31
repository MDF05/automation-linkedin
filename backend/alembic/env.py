"""
Alembic environment script — async SQLAlchemy with asyncpg.

DATABASE_URL is read from environment variables at runtime so the same
alembic.ini works across all environments without modification.
"""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool
from alembic import context

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Read DATABASE_URL from environment and ensure it uses asyncpg driver
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    # Ensure async driver is used (replace plain postgresql:// with asyncpg)
    if "postgresql://" in database_url and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    config.set_main_option("sqlalchemy.url", database_url)

# Import Base from models/base.py so target_metadata is populated
from app.models.base import Base  # noqa: E402
from app.models import (  # noqa: F401 — ensure all models are registered
    Post,
    BotLog,
    Interaction,
    JobApplication,
    Schedule,
    AiUsage,
    Settings,
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no live DB needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside a connection."""
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection) -> None:
    """Configure Alembic context and run the actual migrations (sync callback)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Entry point for 'online' mode — delegates to the async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
