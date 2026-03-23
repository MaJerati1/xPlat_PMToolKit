"""Integration tests for Before Meeting API endpoints.

Tests meeting CRUD, agenda management, attendees, and agenda text parsing.
Database setup and client fixtures are provided by conftest.py.
"""

import pytest
from uuid import uuid4


# ============================================
# MEETING CRUD TESTS
# ============================================

class TestMeetingCRUD:
    """Test meeting create, read, update, delete operations."""

    @pytest.mark.asyncio
    async def test_create_meeting_minimal(self, client):
        """Create a meeting with just a title."""
        resp = await client.post("/api/meetings", json={"title": "Standup"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Standup"
        assert data["status"] == "scheduled"
        assert data["agenda_items"] == []
        assert data["attendees"] == []
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_create_meeting_full(self, client):
        """Create a meeting with all fields, agenda items, and attendees."""
        resp = await client.post("/api/meetings", json={
            "title": "Q2 Planning",
            "date": "2026-04-01",
            "time": "10:00:00",
            "duration_minutes": 60,
            "meeting_link": "https://zoom.us/j/123",
            "notes": "Quarterly planning session",
            "agenda_items": [
                {"title": "Revenue Review", "time_allocation_minutes": 15},
                {"title": "Hiring Plan", "time_allocation_minutes": 20},
            ],
            "attendees": [
                {"email": "alice@company.com", "role": "facilitator"},
                {"email": "bob@company.com"},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Q2 Planning"
        assert data["duration_minutes"] == 60
        assert len(data["agenda_items"]) == 2
        assert len(data["attendees"]) == 2
        assert data["total_agenda_time"] == 35
        assert data["agenda_items"][0]["title"] == "Revenue Review"
        assert data["attendees"][0]["email"] == "alice@company.com"

    @pytest.mark.asyncio
    async def test_get_meeting(self, client):
        """Get a meeting by ID."""
        create_resp = await client.post("/api/meetings", json={"title": "Test Meeting"})
        meeting_id = create_resp.json()["id"]

        resp = await client.get(f"/api/meetings/{meeting_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Meeting"

    @pytest.mark.asyncio
    async def test_get_meeting_not_found(self, client):
        """Get a non-existent meeting returns 404."""
        fake_id = str(uuid4())
        resp = await client.get(f"/api/meetings/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_meetings_empty(self, client):
        """List meetings when none exist."""
        resp = await client.get("/api/meetings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meetings"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_meetings_pagination(self, client):
        """Create 5 meetings and verify pagination."""
        for i in range(5):
            await client.post("/api/meetings", json={"title": f"Meeting {i}"})

        resp = await client.get("/api/meetings?page=1&per_page=2")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["meetings"]) == 2
        assert data["total_pages"] == 3

    @pytest.mark.asyncio
    async def test_update_meeting(self, client):
        """Update meeting fields."""
        create_resp = await client.post("/api/meetings", json={"title": "Original"})
        meeting_id = create_resp.json()["id"]

        resp = await client.patch(f"/api/meetings/{meeting_id}", json={
            "title": "Updated Title",
            "duration_minutes": 90,
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"
        assert resp.json()["duration_minutes"] == 90

    @pytest.mark.asyncio
    async def test_delete_meeting(self, client):
        """Delete a meeting."""
        create_resp = await client.post("/api/meetings", json={"title": "To Delete"})
        meeting_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/meetings/{meeting_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/meetings/{meeting_id}")
        assert resp.status_code == 404


# ============================================
# AGENDA ITEM TESTS
# ============================================

class TestAgendaItems:
    """Test agenda item CRUD and parsing."""

    @pytest.mark.asyncio
    async def test_add_agenda_items(self, client):
        """Add agenda items to an existing meeting."""
        create_resp = await client.post("/api/meetings", json={"title": "Test"})
        meeting_id = create_resp.json()["id"]

        resp = await client.post(f"/api/meetings/{meeting_id}/agenda", json=[
            {"title": "Item A", "time_allocation_minutes": 10},
            {"title": "Item B", "time_allocation_minutes": 20},
        ])
        assert resp.status_code == 201
        items = resp.json()
        assert len(items) == 2
        assert items[0]["title"] == "Item A"
        assert items[1]["title"] == "Item B"

    @pytest.mark.asyncio
    async def test_get_agenda_items(self, client):
        """Get agenda items ordered by position."""
        create_resp = await client.post("/api/meetings", json={
            "title": "Test",
            "agenda_items": [
                {"title": "First"},
                {"title": "Second"},
                {"title": "Third"},
            ],
        })
        meeting_id = create_resp.json()["id"]

        resp = await client.get(f"/api/meetings/{meeting_id}/agenda")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 3
        assert items[0]["title"] == "First"
        assert items[2]["title"] == "Third"

    @pytest.mark.asyncio
    async def test_update_agenda_item(self, client):
        """Update a single agenda item."""
        create_resp = await client.post("/api/meetings", json={
            "title": "Test",
            "agenda_items": [{"title": "Original"}],
        })
        meeting_id = create_resp.json()["id"]
        item_id = create_resp.json()["agenda_items"][0]["id"]

        resp = await client.patch(f"/api/meetings/{meeting_id}/agenda/{item_id}", json={
            "title": "Updated",
            "status": "discussed",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"
        assert resp.json()["status"] == "discussed"

    @pytest.mark.asyncio
    async def test_delete_agenda_item(self, client):
        """Delete a single agenda item."""
        create_resp = await client.post("/api/meetings", json={
            "title": "Test",
            "agenda_items": [{"title": "To Delete"}, {"title": "Keep"}],
        })
        meeting_id = create_resp.json()["id"]
        item_id = create_resp.json()["agenda_items"][0]["id"]

        resp = await client.delete(f"/api/meetings/{meeting_id}/agenda/{item_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/meetings/{meeting_id}/agenda")
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_reorder_agenda_items(self, client):
        """Reorder agenda items."""
        create_resp = await client.post("/api/meetings", json={
            "title": "Test",
            "agenda_items": [{"title": "A"}, {"title": "B"}, {"title": "C"}],
        })
        meeting_id = create_resp.json()["id"]
        ids = [item["id"] for item in create_resp.json()["agenda_items"]]

        # Reverse the order
        resp = await client.put(f"/api/meetings/{meeting_id}/agenda/reorder", json={
            "item_ids": list(reversed(ids)),
        })
        assert resp.status_code == 200
        items = resp.json()
        assert items[0]["title"] == "C"
        assert items[1]["title"] == "B"
        assert items[2]["title"] == "A"

    @pytest.mark.asyncio
    async def test_parse_agenda_text(self, client):
        """Parse freeform text into structured agenda items."""
        create_resp = await client.post("/api/meetings", json={"title": "Test"})
        meeting_id = create_resp.json()["id"]

        resp = await client.post(f"/api/meetings/{meeting_id}/agenda/parse", json={
            "text": """
1. Revenue Review (15 min)
2. Hiring Plan (20 min)
   - Engineering team
   - Sales team
3. Roadmap Update
            """,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["parse_method"] == "rule_based"
        assert len(data["items"]) == 3
        assert data["items"][0]["title"] == "Revenue Review"
        assert data["items"][0]["time_allocation_minutes"] == 15
        assert data["items"][1]["time_allocation_minutes"] == 20
        assert "Engineering team" in data["items"][1]["description"]


# ============================================
# ATTENDEE TESTS
# ============================================

class TestAttendees:
    """Test attendee management."""

    @pytest.mark.asyncio
    async def test_add_attendees(self, client):
        """Add attendees to a meeting."""
        create_resp = await client.post("/api/meetings", json={"title": "Test"})
        meeting_id = create_resp.json()["id"]

        resp = await client.post(f"/api/meetings/{meeting_id}/attendees", json=[
            {"email": "alice@test.com", "name": "Alice", "role": "facilitator"},
            {"email": "bob@test.com", "name": "Bob"},
        ])
        assert resp.status_code == 201
        assert len(resp.json()) == 2
        assert resp.json()[0]["email"] == "alice@test.com"
        assert resp.json()[0]["role"] == "facilitator"
        assert resp.json()[1]["role"] == "attendee"

    @pytest.mark.asyncio
    async def test_duplicate_attendee_skipped(self, client):
        """Adding a duplicate email is silently skipped."""
        create_resp = await client.post("/api/meetings", json={
            "title": "Test",
            "attendees": [{"email": "alice@test.com"}],
        })
        meeting_id = create_resp.json()["id"]

        resp = await client.post(f"/api/meetings/{meeting_id}/attendees", json=[
            {"email": "alice@test.com"},  # Duplicate
            {"email": "bob@test.com"},    # New
        ])
        assert resp.status_code == 201
        assert len(resp.json()) == 1  # Only Bob was added

    @pytest.mark.asyncio
    async def test_remove_attendee(self, client):
        """Remove an attendee from a meeting."""
        create_resp = await client.post("/api/meetings", json={
            "title": "Test",
            "attendees": [{"email": "alice@test.com"}, {"email": "bob@test.com"}],
        })
        meeting_id = create_resp.json()["id"]
        attendee_id = create_resp.json()["attendees"][0]["id"]

        resp = await client.delete(f"/api/meetings/{meeting_id}/attendees/{attendee_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/meetings/{meeting_id}/attendees")
        assert len(resp.json()) == 1
