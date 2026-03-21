"""
Shared pytest fixtures and configuration.
"""
import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db


# Database setup for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Create a new database session for a test."""
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """Create an async HTTP client for testing the API."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Fixture with sample user data."""
    return {
        "email": "test@example.com",
        "name": "Test User",
        "password": "TestPassword123",
    }


@pytest.fixture
def test_post_data():
    """Fixture with sample post data."""
    return {
        "caption": "Test post with #multipost",
        "media_urls": ["https://example.com/image.jpg"],
        "media_type": "image",
        "platforms": ["instagram", "tiktok"],
    }


@pytest.fixture
def test_channel_data():
    """Fixture with sample channel data."""
    return {
        "platform": "instagram",
        "username": "@testaccount",
        "account_id": "123456789",
        "is_active": True,
    }
