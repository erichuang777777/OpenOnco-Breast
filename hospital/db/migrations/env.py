"""Alembic environment configuration.

Reads DATABASE_URL from environment / hospital.config, imports the
SQLAlchemy Base so autogenerate can detect schema changes.

Usage (production):
    DATABASE_URL=postgresql+asyncpg://... alembic upgrade head

Usage (generate new revision):
    DATABASE_URL=postgresql+asyncpg://... alembic revision --autogenerate -m "describe change"
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Import metadata from the app ─────────────────────────────────────────────
from hospital.db.models import Base
from hospital.config import get_settings

target_metadata = Base.metadata

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow DATABASE_URL override from environment (required for async URL → sync for Alembic).
# Convert async drivers to synchronous equivalents for migration runner.
_db_url = get_settings().DATABASE_URL
_sync_url = (
    _db_url
    .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    .replace("sqlite+aiosqlite://", "sqlite://")
)
config.set_main_option("sqlalchemy.url", _sync_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (requires live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
