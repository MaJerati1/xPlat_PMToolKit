"""Smoke tests for Meeting Toolkit API."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_health_check(client: AsyncClient):
    """Health endpoint returns 200 with correct payload."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "meeting-toolkit-api"


@pytest.mark.anyio
async def test_api_docs_available(client: AsyncClient):
    """Swagger docs are accessible."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_before_meeting_routes_exist(client: AsyncClient):
    """Before Meeting endpoints are registered."""
    response = await client.get("/api/calendar/events")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_transcript_upload_requires_input(client: AsyncClient):
    """Transcript upload rejects empty requests."""
    response = await client.post("/api/meetings/00000000-0000-0000-0000-000000000001/transcript")
    assert response.status_code == 422 or response.status_code == 400
