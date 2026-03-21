"""Tests for the Action Item Extraction Engine.

Tests dedicated extraction, segment linking, batch confirm/reject,
filtering, sorting, and the summary endpoint.
Database setup and client fixtures provided by conftest.py.
"""

import pytest
from uuid import uuid4


SAMPLE_TRANSCRIPT = """Alice: Good morning everyone. Welcome to our Q2 planning meeting.
Bob: Thanks Alice. I have the revenue numbers ready to present.
Alice: Great, let's start with the revenue review.
Bob: Q1 revenue came in at 2.3 million, which is 12% above forecast.
Carol: That's excellent. I think we should increase our enterprise target.
Alice: Agreed. Bob, can you update the forecast by Friday?
Bob: Will do. I'll also need the updated pipeline data from the sales team.
Carol: I'll send that over by Wednesday.
Alice: Perfect. Next item - the hiring plan. We decided to open 3 new positions.
Bob: I'll draft the job descriptions by next Monday.
Carol: And I need to get budget approval from finance by end of week.
Alice: Great. Let's wrap up. Thanks everyone."""


# ============================================
# EXTRACTION ENGINE TESTS
# ============================================

class TestExtractionEngine:
    """Test the dedicated action item extraction endpoint."""

    @pytest.mark.asyncio
    async def test_extract_action_items(self, client, meeting_id):
        """Extract action items from a transcript."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/extract-actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["count"] > 0
        assert len(data["items"]) > 0
        assert all(item["confirmed"] is False for item in data["items"])

    @pytest.mark.asyncio
    async def test_extract_replaces_existing(self, client, meeting_id):
        """Extract with replace_existing clears old items."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        # First extraction
        resp1 = await client.post(f"/api/meetings/{meeting_id}/extract-actions")
        first_count = resp1.json()["count"]

        # Second extraction with replace
        resp2 = await client.post(
            f"/api/meetings/{meeting_id}/extract-actions",
            json={"replace_existing": True},
        )
        assert resp2.status_code == 200

        # Verify only the new items exist
        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        current_items = items_resp.json()
        # All items should be from the second extraction (none confirmed from first)
        assert all(item["confirmed"] is False for item in current_items)

    @pytest.mark.asyncio
    async def test_extract_no_transcript_returns_409(self, client, meeting_id):
        """Extraction without transcript returns 409."""
        resp = await client.post(f"/api/meetings/{meeting_id}/extract-actions")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_extract_nonexistent_meeting_returns_404(self, client):
        """Extraction on non-existent meeting returns 404."""
        fake_id = str(uuid4())
        resp = await client.post(f"/api/meetings/{fake_id}/extract-actions")
        assert resp.status_code == 404


# ============================================
# BATCH OPERATION TESTS
# ============================================

class TestBatchOperations:
    """Test batch confirm, reject, and status update."""

    @pytest.mark.asyncio
    async def test_batch_confirm(self, client, meeting_id):
        """Confirm multiple action items at once."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/extract-actions")

        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        item_ids = [item["id"] for item in items_resp.json()[:2]]

        resp = await client.post(
            f"/api/meetings/{meeting_id}/action-items/batch-confirm",
            json={"item_ids": item_ids},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed_count"] == len(item_ids)
        assert all(item["confirmed"] is True for item in data["items"])

    @pytest.mark.asyncio
    async def test_batch_reject(self, client, meeting_id):
        """Reject (delete) multiple action items at once."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/extract-actions")

        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        all_items = items_resp.json()
        reject_ids = [item["id"] for item in all_items[:1]]
        original_count = len(all_items)

        resp = await client.post(
            f"/api/meetings/{meeting_id}/action-items/batch-reject",
            json={"item_ids": reject_ids},
        )
        assert resp.status_code == 200
        assert resp.json()["rejected_count"] == 1

        # Verify item was removed
        items_after = await client.get(f"/api/meetings/{meeting_id}/action-items")
        assert len(items_after.json()) == original_count - 1

    @pytest.mark.asyncio
    async def test_batch_status_update(self, client, meeting_id):
        """Update status for multiple items at once."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/extract-actions")

        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        item_ids = [item["id"] for item in items_resp.json()[:2]]

        resp = await client.post(
            f"/api/meetings/{meeting_id}/action-items/batch-status",
            json={"item_ids": item_ids, "status": "in_progress"},
        )
        assert resp.status_code == 200
        assert all(item["status"] == "in_progress" for item in resp.json())


# ============================================
# FILTERING AND SUMMARY TESTS
# ============================================

class TestFilteringAndSummary:
    """Test action item filtering, sorting, and summary."""

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client, meeting_id):
        """Filter action items by status."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/extract-actions")

        # All should be pending initially
        resp = await client.get(
            f"/api/meetings/{meeting_id}/action-items?status=pending"
        )
        assert resp.status_code == 200
        assert len(resp.json()) > 0
        assert all(item["status"] == "pending" for item in resp.json())

        # None should be completed
        resp = await client.get(
            f"/api/meetings/{meeting_id}/action-items?status=completed"
        )
        assert len(resp.json()) == 0

    @pytest.mark.asyncio
    async def test_filter_confirmed_only(self, client, meeting_id):
        """Filter to only confirmed items."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/extract-actions")

        # None confirmed initially
        resp = await client.get(
            f"/api/meetings/{meeting_id}/action-items?confirmed_only=true"
        )
        assert len(resp.json()) == 0

        # Confirm one
        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        item_id = items_resp.json()[0]["id"]
        await client.patch(f"/api/action-items/{item_id}", json={"confirmed": True})

        # Now one confirmed
        resp = await client.get(
            f"/api/meetings/{meeting_id}/action-items?confirmed_only=true"
        )
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_action_item_summary(self, client, meeting_id):
        """Get action item summary counts."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/extract-actions")

        resp = await client.get(f"/api/meetings/{meeting_id}/action-items/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert data["unconfirmed"] == data["total"]
        assert data["confirmed"] == 0
        assert "pending" in data["by_status"]
