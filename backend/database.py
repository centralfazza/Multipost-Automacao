"""
Async SQLAlchemy database setup.
Supports PostgreSQL (Supabase) in production and SQLite in development.
"""
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./multipost.db")

# Normalize postgres:// → asyncpg, strip sslmode from URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Remove sslmode param (asyncpg receives it separately)
if "sslmode=" in DATABASE_URL:
    parts = DATABASE_URL.split("?")
    params = [p for p in parts[1].split("&") if not p.startswith("sslmode=")]
    DATABASE_URL = parts[0] + ("?" + "&".join(params) if params else "")

IS_PRODUCTION = os.getenv("VERCEL") or os.getenv("RAILWAY_ENVIRONMENT")

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool if IS_PRODUCTION else None,
    pool_pre_ping=not bool(IS_PRODUCTION),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
