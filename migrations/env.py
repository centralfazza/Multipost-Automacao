"""
Alembic environment configuration.
Reads DATABASE_URL from .env and uses the backend models for autogenerate.
"""
import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure project root is on sys.path so 'backend' is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from backend.database import Base
from backend import models  # noqa: F401 — registers all models on Base.metadata

config = context.config

# Override sqlalchemy.url from env var (so we don't hardcode credentials)
db_url = os.getenv("DATABASE_URL", "sqlite:///./multipost.db")
# Alembic uses sync drivers — normalize async URLs to sync equivalents
db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
db_url = db_url.replace("sqlite+aiosqlite:///", "sqlite:///")
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
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
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
