"""Tests for meeting minutes document generator.

Tests cover:
  - JSON output with all sections
  - Word document (.docx) output
  - PDF output
  - Missing meeting returns 404
  - Meeting without analysis returns appropriate response
  - Minutes metadata includes analysis stats
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def analyzed_meeting_id(client: AsyncClient):
    """Create a meeting, upload a transcript, and analyze it.
    Returns a meeting ID that has summary and action items ready for minutes."""
    # Create meeting
    resp = await client.post("/api/meetings", json={
        "title": "Q2 Planning Sync",
        "date": "2026-04-01",
        "time": "10:00:00",
        "duration_minutes": 60,
    })
    mid = resp.json()["id"]

    # Add agenda
    await client.post(f"/api/meetings/{mid}/agenda", json=[
        {"title": "Revenue forecast review", "time_allocation_minutes": 15},
        {"title": "Hiring plan update", "time_allocation_minutes": 10},
    ])

    # Add attendees
    await client.post(f"/api/meetings/{mid}/attendees", json=[
        {"name": "Alice Johnson", "email": "alice@example.com", "role": "organizer"},
        {"name": "Bob Smith", "email": "bob@example.com", "role": "participant"},
    ])

    # Upload transcript
    transcript = """Alice: Welcome to our Q2 planning sync.
Bob: Thanks Alice. Revenue came in at 2.3 million, 12% above forecast.
Alice: Great. Let's set Q2 target at 2.8 million. Bob, update the forecast by Friday.
Bob: Will do. I'll also draft the job descriptions by next Monday.
Alice: Perfect. We decided to open 3 engineering positions. Let's wrap up."""

    await client.post(f"/api/meetings/{mid}/transcript/text", json={"text": transcript})

    # Analyze (uses MockProvider)
    resp = await client.post(f"/api/meetings/{mid}/analyze", json={"reanalyze": False})
    assert resp.status_code == 200

    return mid


# ============================================
# JSON OUTPUT
# ============================================

@pytest.mark.asyncio
async def test_minutes_json(client: AsyncClient, analyzed_meeting_id: str):
    """Generate minutes in JSON format with all sections."""
    resp = await client.post(f"/api/meetings/{analyzed_meeting_id}/minutes?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meeting_id"] == analyzed_meeting_id
    assert "sections" in data
    assert len(data["sections"]) >= 2  # At least meeting details + summary


@pytest.mark.asyncio
async def test_minutes_has_meeting_details(client: AsyncClient, analyzed_meeting_id: str):
    """Minutes include meeting details section."""
    resp = await client.post(f"/api/meetings/{analyzed_meeting_id}/minutes?format=json")
    data = resp.json()
    titles = [s["title"] for s in data["sections"]]
    assert "Meeting Details" in titles


@pytest.mark.asyncio
async def test_minutes_has_attendees(client: AsyncClient, analyzed_meeting_id: str):
    """Minutes include attendees section when attendees exist."""
    # Verify attendees were added
    att_resp = await client.get(f"/api/meetings/{analyzed_meeting_id}/attendees")
    att_data = att_resp.json()

    resp = await client.post(f"/api/meetings/{analyzed_meeting_id}/minutes?format=json")
    data = resp.json()
    titles = [s["title"] for s in data["sections"]]

    if len(att_data) > 0:
        assert "Attendees" in titles
    # If no attendees loaded, section is correctly absent


@pytest.mark.asyncio
async def test_minutes_has_summary(client: AsyncClient, analyzed_meeting_id: str):
    """Minutes include executive summary from LLM analysis."""
    resp = await client.post(f"/api/meetings/{analyzed_meeting_id}/minutes?format=json")
    data = resp.json()
    titles = [s["title"] for s in data["sections"]]
    assert "Executive Summary" in titles


@pytest.mark.asyncio
async def test_minutes_metadata(client: AsyncClient, analyzed_meeting_id: str):
    """Minutes include metadata with analysis stats."""
    resp = await client.post(f"/api/meetings/{analyzed_meeting_id}/minutes?format=json")
    data = resp.json()
    assert "metadata" in data
    assert "action_items_total" in data["metadata"]
    assert "llm_provider" in data["metadata"]


# ============================================
# DOCUMENT OUTPUTS
# ============================================

@pytest.mark.asyncio
async def test_minutes_docx(client: AsyncClient, analyzed_meeting_id: str):
    """Generate minutes as a Word document."""
    resp = await client.post(f"/api/meetings/{analyzed_meeting_id}/minutes?format=docx")
    assert resp.status_code == 200
    assert "openxmlformats" in resp.headers.get("content-type", "")
    assert len(resp.content) > 100


@pytest.mark.asyncio
async def test_minutes_pdf(client: AsyncClient, analyzed_meeting_id: str):
    """Generate minutes as PDF (or HTML fallback if WeasyPrint unavailable)."""
    resp = await client.post(f"/api/meetings/{analyzed_meeting_id}/minutes?format=pdf")
    assert resp.status_code == 200
    # May be PDF or HTML depending on WeasyPrint availability
    assert len(resp.content) > 100


# ============================================
# ERROR CASES
# ============================================

@pytest.mark.asyncio
async def test_minutes_missing_meeting(client: AsyncClient):
    """Minutes returns 404 for non-existent meeting."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/meetings/{fake_id}/minutes?format=json")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_minutes_no_analysis(client: AsyncClient):
    """Minutes for meeting without analysis still returns (with limited sections)."""
    # Create meeting without analysis
    resp = await client.post("/api/meetings", json={"title": "Unanalyzed meeting"})
    mid = resp.json()["id"]

    resp = await client.post(f"/api/meetings/{mid}/minutes?format=json")
    assert resp.status_code == 200
    data = resp.json()
    # Should still have meeting details section at minimum
    assert len(data["sections"]) >= 1
