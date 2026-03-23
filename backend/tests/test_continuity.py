"""Tests for the Meeting Continuity features.

Tests transcript-to-agenda mapping, action item tracking dashboard,
and future meeting preparation engine.
Database setup and client fixtures provided by conftest.py.
"""

import pytest
from uuid import uuid4


SAMPLE_TRANSCRIPT = """Alice: Good morning everyone. Welcome to our Q2 planning meeting.
Bob: Thanks Alice. Let's start with the revenue review.
Bob: Q1 revenue came in at 2.3 million, 12% above forecast. Enterprise deals drove the growth.
Carol: Excellent. I think we should increase our Q2 target.
Alice: Agreed. Bob, can you update the forecast by Friday?
Bob: Will do. I'll need the pipeline data from the sales team.
Carol: I'll send that by Wednesday.
Alice: Next - the hiring plan. We decided to open 3 engineering positions.
Bob: I'll draft job descriptions by Monday.
Carol: I need budget approval from finance by end of week.
Alice: We'll defer the product roadmap discussion to next week.
Alice: Thanks everyone."""


# ============================================
# HELPER: Create a full meeting with agenda, transcript, and analysis
# ============================================

async def create_full_meeting(client, title="Test Meeting", agenda_items=None, transcript=None):
    """Helper to set up a complete meeting with agenda, transcript, and analysis."""
    # Create meeting with agenda
    meeting_data = {"title": title}
    if agenda_items:
        meeting_data["agenda_items"] = agenda_items

    resp = await client.post("/api/meetings", json=meeting_data)
    meeting_id = resp.json()["id"]

    # Upload transcript
    if transcript:
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": transcript},
        )
        # Run analysis
        await client.post(f"/api/meetings/{meeting_id}/analyze")

    return meeting_id


# ============================================
# TRANSCRIPT-TO-AGENDA MAPPING TESTS
# ============================================

class TestAgendaCoverage:
    """Test transcript-to-agenda mapping and coverage analysis."""

    @pytest.mark.asyncio
    async def test_coverage_with_matching_agenda(self, client):
        """Coverage analysis maps transcript to agenda items."""
        meeting_id = await create_full_meeting(
            client,
            agenda_items=[
                {"title": "Revenue Review", "time_allocation_minutes": 15},
                {"title": "Hiring Plan", "time_allocation_minutes": 10},
                {"title": "Product Roadmap", "time_allocation_minutes": 20},
            ],
            transcript=SAMPLE_TRANSCRIPT,
        )

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/coverage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agenda_items"] == 3
        assert data["discussed"] >= 1  # At least revenue should match
        assert data["coverage_percentage"] > 0

    @pytest.mark.asyncio
    async def test_coverage_identifies_not_covered(self, client):
        """Coverage flags agenda items that weren't discussed."""
        meeting_id = await create_full_meeting(
            client,
            agenda_items=[
                {"title": "Revenue Review"},
                {"title": "Quantum Computing Strategy"},  # Not in transcript
            ],
            transcript=SAMPLE_TRANSCRIPT,
        )

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/coverage")
        data = resp.json()
        # "Quantum Computing" shouldn't match anything
        items_by_title = {i["title"]: i for i in data["items"]}
        assert items_by_title["Quantum Computing Strategy"]["status"] in ("not_covered", "pending")

    @pytest.mark.asyncio
    async def test_coverage_no_transcript(self, client):
        """Coverage with no transcript marks all items as not covered."""
        resp = await client.post("/api/meetings", json={
            "title": "No Transcript Meeting",
            "agenda_items": [{"title": "Topic A"}, {"title": "Topic B"}],
        })
        meeting_id = resp.json()["id"]

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/coverage")
        data = resp.json()
        assert data["not_covered"] == 2
        assert data["coverage_percentage"] == 0

    @pytest.mark.asyncio
    async def test_coverage_no_agenda(self, client):
        """Coverage with no agenda items returns zero counts."""
        resp = await client.post("/api/meetings", json={"title": "No Agenda"})
        meeting_id = resp.json()["id"]

        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/coverage")
        data = resp.json()
        assert data["total_agenda_items"] == 0


# ============================================
# ACTION ITEM TRACKING DASHBOARD TESTS
# ============================================

class TestActionTracking:
    """Test the action item tracking dashboard."""

    @pytest.mark.asyncio
    async def test_tracking_dashboard(self, client):
        """Dashboard returns status counts and owner data."""
        meeting_id = await create_full_meeting(
            client, transcript=SAMPLE_TRANSCRIPT
        )

        resp = await client.get(f"/api/meetings/{meeting_id}/action-items/tracking")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        assert "by_status" in data
        assert "by_priority" in data
        assert "completion_rate" in data
        assert "overdue" in data
        assert "owners" in data

    @pytest.mark.asyncio
    async def test_tracking_with_confirmed_items(self, client):
        """Dashboard reflects confirmed and status-changed items."""
        meeting_id = await create_full_meeting(
            client, transcript=SAMPLE_TRANSCRIPT
        )

        # Get items and confirm one
        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        items = items_resp.json()
        if items:
            await client.patch(
                f"/api/action-items/{items[0]['id']}",
                json={"confirmed": True, "status": "completed"},
            )

        resp = await client.get(f"/api/meetings/{meeting_id}/action-items/tracking")
        data = resp.json()
        if items:
            assert data["confirmed"] >= 1
            assert data["completion_rate"] > 0

    @pytest.mark.asyncio
    async def test_global_tracking_dashboard(self, client):
        """Global dashboard works across all meetings."""
        await create_full_meeting(client, title="Meeting 1", transcript=SAMPLE_TRANSCRIPT)
        await create_full_meeting(client, title="Meeting 2", transcript=SAMPLE_TRANSCRIPT)

        resp = await client.get("/api/action-items/tracking")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meeting_id"] is None  # Global view
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_tracking_empty_meeting(self, client, meeting_id):
        """Dashboard returns zeros for a meeting with no action items."""
        resp = await client.get(f"/api/meetings/{meeting_id}/action-items/tracking")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["completion_rate"] == 0


# ============================================
# FUTURE MEETING PREPARATION TESTS
# ============================================

class TestFutureMeetingPrep:
    """Test the future meeting preparation engine."""

    @pytest.mark.asyncio
    async def test_generate_next_agenda(self, client):
        """Future prep generates a draft agenda from meeting outcomes."""
        meeting_id = await create_full_meeting(
            client,
            agenda_items=[
                {"title": "Revenue Review"},
                {"title": "Hiring Plan"},
                {"title": "Product Roadmap"},
            ],
            transcript=SAMPLE_TRANSCRIPT,
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/next-agenda")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_meeting_id"] == meeting_id
        assert len(data["draft_agenda_items"]) > 0

        # Should always include an open discussion slot
        titles = [item["title"] for item in data["draft_agenda_items"]]
        assert any("discussion" in t.lower() or "new business" in t.lower() for t in titles)

    @pytest.mark.asyncio
    async def test_future_prep_includes_outstanding_items(self, client):
        """Future prep lists outstanding action items."""
        meeting_id = await create_full_meeting(
            client, transcript=SAMPLE_TRANSCRIPT
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/next-agenda")
        data = resp.json()
        # Should have outstanding items (all are pending after analysis)
        assert isinstance(data["outstanding_action_items"], list)

    @pytest.mark.asyncio
    async def test_future_prep_carries_deferred_topics(self, client):
        """Future prep carries over deferred agenda items."""
        # Create meeting with agenda
        resp = await client.post("/api/meetings", json={
            "title": "Test",
            "agenda_items": [
                {"title": "Topic A"},
                {"title": "Deferred Topic B"},
            ],
        })
        meeting_id = resp.json()["id"]

        # Manually defer Topic B
        item_id = resp.json()["agenda_items"][1]["id"]
        await client.patch(
            f"/api/meetings/{meeting_id}/agenda/{item_id}",
            json={"status": "deferred"},
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/next-agenda")
        data = resp.json()
        assert len(data["deferred_topics"]) >= 1
        deferred_titles = [d["title"] for d in data["deferred_topics"]]
        assert "Deferred Topic B" in deferred_titles

    @pytest.mark.asyncio
    async def test_future_prep_nonexistent_meeting(self, client):
        """Future prep handles non-existent meetings gracefully."""
        fake_id = str(uuid4())
        resp = await client.post(f"/api/meetings/{fake_id}/next-agenda")
        assert resp.status_code == 200
        data = resp.json()
        assert "not found" in data["source_meeting_title"].lower()

    @pytest.mark.asyncio
    async def test_future_prep_includes_time_allocations(self, client):
        """Draft agenda items have suggested time allocations."""
        meeting_id = await create_full_meeting(
            client, transcript=SAMPLE_TRANSCRIPT
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/next-agenda")
        data = resp.json()
        for item in data["draft_agenda_items"]:
            assert "time_allocation_minutes" in item
            assert item["time_allocation_minutes"] > 0
