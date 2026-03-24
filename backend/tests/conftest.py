"""Shared test configuration for all API integration tests.

Provides a single in-memory SQLite database, async session, and HTTP client
that all test files share. This avoids the issue where multiple test files
each create separate engines and fight over app.dependency_overrides.
"""

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.config import settings
from app.main import app as fastapi_app

# Ensure all models are registered with Base.metadata
from app.models import (  # noqa: F401
    Organization, User, Meeting, AgendaItem, MeetingAttendee, Document,
    Transcript, TranscriptSegment,
    MeetingSummary, ActionItem,
)

# ============================================
# FORCE MOCK PROVIDER IN TESTS
# Always use MockProvider regardless of what .env has configured.
# Tests should never call real LLM APIs.
# ============================================
settings.ANTHROPIC_API_KEY = ""
settings.OPENAI_API_KEY = ""


# ============================================
# SHARED TEST DATABASE (single engine for all tests)
# ============================================

TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement in SQLite (off by default)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def override_get_db():
    """FastAPI dependency override that uses the test database."""
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Apply the override once for all tests
fastapi_app.dependency_overrides[get_db] = override_get_db


# ============================================
# SHARED FIXTURES
# ============================================

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after. Applies to all test files."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client shared by all test files."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def meeting_id(client):
    """Create a meeting and return its ID. Shared helper fixture."""
    resp = await client.post("/api/meetings", json={"title": "Test Meeting"})
    return resp.json()["id"]


@pytest_asyncio.fixture
async def sample_meeting_id(client):
    """Create a meeting with agenda items and return its ID.

    Used by document gathering and briefing tests that need a
    populated meeting to work with.
    """
    # Create meeting
    resp = await client.post("/api/meetings", json={
        "title": "Q2 Planning Sync",
        "date": "2026-04-01",
        "time": "10:00:00",
        "duration_minutes": 60,
    })
    mid = resp.json()["id"]

    # Add agenda items
    await client.post(f"/api/meetings/{mid}/agenda", json=[
        {"title": "Revenue forecast review", "time_allocation_minutes": 15},
        {"title": "Hiring plan update", "time_allocation_minutes": 10},
        {"title": "Product roadmap priorities", "time_allocation_minutes": 20},
        {"title": "Engineering sprint review", "time_allocation_minutes": 15},
    ])

    # Add an attendee
    await client.post(f"/api/meetings/{mid}/attendees", json=[
        {"name": "Alice Johnson", "email": "alice@example.com", "role": "organizer"},
        {"name": "Bob Smith", "email": "bob@example.com", "role": "participant"},
    ])

    return mid
