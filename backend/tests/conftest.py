"""Test fixtures and configuration."""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app

# Import all models to ensure they're registered with Base.metadata
# This must happen before create_all is called
from app.models import (  # noqa: F401
    AIInvestigation,
    Document,
    DocumentChunk,
    Incident,
    IncidentEvent,
    IncidentEvidence,
    Postmortem,
    Repository,
    User,
)

# Use DATABASE_URL from environment if available (for CI with Postgres + pgvector)
# Fall back to SQLite for local development (but pgvector features won't work)
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///:memory:"
)

# Check if using Postgres (for pgvector support)
USING_POSTGRES = TEST_DATABASE_URL.startswith("postgresql")


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # SQLite needs check_same_thread=False, Postgres doesn't use this option
    connect_args = {} if USING_POSTGRES else {"check_same_thread": False}

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        **({"connect_args": connect_args} if connect_args else {}),
    )

    async with engine.begin() as conn:
        # Enable pgvector extension for Postgres
        if USING_POSTGRES:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    """Create authorization headers for the test user."""
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}
