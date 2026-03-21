"""Tests for the Quick Analyze endpoint.

Tests the single-request analysis flow: text in, full results out.
Database setup and client fixtures provided by conftest.py.
"""

import pytest


SAMPLE_TRANSCRIPT = """Alice: Good morning everyone. Welcome to our Q2 planning meeting.
Bob: Thanks Alice. I have the revenue numbers ready.
Alice: Great, let's start with the revenue review.
Bob: Q1 revenue was 2.3 million, 12% above forecast. Enterprise deals drove the growth.
Carol: Excellent. I think we should increase our Q2 target.
Alice: Agreed. Bob, can you update the forecast by Friday?
Bob: Will do. I'll need the pipeline data from sales.
Carol: I'll send that by Wednesday.
Alice: Next - hiring. We decided to open 3 engineering positions.
Bob: I'll draft job descriptions by Monday.
Carol: I need budget approval from finance by end of week.
Alice: Great meeting. Thanks everyone."""


class TestQuickAnalyze:
    """Test the single-request quick analysis endpoint."""

    @pytest.mark.asyncio
    async def test_quick_analyze_basic(self, client):
        """Quick analyze returns full results from plain text."""
        resp = await client.post("/api/quick-analyze", json={
            "text": SAMPLE_TRANSCRIPT,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["meeting_id"] is not None
        assert data["summary"] is not None
        assert data["summary"]["text"] is not None
        assert len(data["summary"]["text"]) > 0
        assert data["transcript_info"]["segments"] > 0
        assert data["transcript_info"]["speakers"] > 0

    @pytest.mark.asyncio
    async def test_quick_analyze_returns_action_items(self, client):
        """Quick analyze extracts action items."""
        resp = await client.post("/api/quick-analyze", json={
            "text": SAMPLE_TRANSCRIPT,
        })
        data = resp.json()
        assert len(data["action_items"]) > 0
        for item in data["action_items"]:
            assert "task" in item
            assert "priority" in item

    @pytest.mark.asyncio
    async def test_quick_analyze_returns_speakers(self, client):
        """Quick analyze identifies speakers."""
        resp = await client.post("/api/quick-analyze", json={
            "text": SAMPLE_TRANSCRIPT,
        })
        data = resp.json()
        assert len(data["speakers"]) > 0

    @pytest.mark.asyncio
    async def test_quick_analyze_returns_decisions(self, client):
        """Quick analyze extracts decisions."""
        resp = await client.post("/api/quick-analyze", json={
            "text": SAMPLE_TRANSCRIPT,
        })
        data = resp.json()
        assert isinstance(data["decisions"], list)

    @pytest.mark.asyncio
    async def test_quick_analyze_with_title(self, client):
        """Quick analyze accepts a custom title."""
        resp = await client.post("/api/quick-analyze", json={
            "text": SAMPLE_TRANSCRIPT,
            "title": "Q2 Planning Session",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_quick_analyze_with_format_hint(self, client):
        """Quick analyze accepts a format hint."""
        resp = await client.post("/api/quick-analyze", json={
            "text": SAMPLE_TRANSCRIPT,
            "format_hint": "txt",
        })
        assert resp.status_code == 200
        assert resp.json()["transcript_info"]["format"] == "txt"

    @pytest.mark.asyncio
    async def test_quick_analyze_srt_format(self, client):
        """Quick analyze handles SRT input."""
        srt = """1
00:00:01,000 --> 00:00:04,500
Alice: Good morning everyone.

2
00:00:05,000 --> 00:00:08,200
Bob: Thanks for joining.

3
00:00:09,000 --> 00:00:15,000
Alice: Let's review the plan.
"""
        resp = await client.post("/api/quick-analyze", json={
            "text": srt,
            "format_hint": "srt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["transcript_info"]["format"] == "srt"

    @pytest.mark.asyncio
    async def test_quick_analyze_empty_text_rejected(self, client):
        """Empty text is rejected with 422."""
        resp = await client.post("/api/quick-analyze", json={"text": "   "})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_quick_analyze_meeting_id_usable(self, client):
        """The returned meeting_id can be used for follow-up API calls."""
        resp = await client.post("/api/quick-analyze", json={
            "text": SAMPLE_TRANSCRIPT,
        })
        meeting_id = resp.json()["meeting_id"]

        # Should be able to get the summary via the standard endpoint
        summary_resp = await client.get(f"/api/meetings/{meeting_id}/summary")
        assert summary_resp.status_code == 200

        # Should be able to get action items
        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        assert items_resp.status_code == 200
