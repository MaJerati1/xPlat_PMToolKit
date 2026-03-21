"""Integration tests for the LLM Analysis Pipeline and After Meeting API.

Tests the full pipeline: upload transcript → analyze → get summary → manage action items.
Uses the MockProvider (no API keys needed) to exercise the complete flow.
Database setup and client fixtures provided by conftest.py.
"""

import pytest
from uuid import uuid4


# ============================================
# SAMPLE DATA
# ============================================

SAMPLE_TRANSCRIPT = """Alice: Good morning everyone. Welcome to our Q2 planning meeting.
Bob: Thanks Alice. I have the revenue numbers ready to present.
Alice: Great, let's start with the revenue review.
Bob: Q1 revenue came in at 2.3 million, which is 12% above forecast. The main driver was enterprise deals.
Carol: That's excellent. I think we should increase our enterprise sales target for Q2.
Alice: Agreed. Let's set the Q2 target at 2.8 million. Bob, can you update the forecast by Friday?
Bob: Will do. I'll also need the updated pipeline data from the sales team.
Carol: I'll send that over by Wednesday.
Alice: Perfect. Next item - the hiring plan. We decided to open 3 new engineering positions.
Bob: I'll draft the job descriptions by next Monday.
Carol: And I need to get budget approval from finance. Should have that sorted by end of week.
Alice: Great. Last item - the product roadmap. Carol, any updates?
Carol: Yes, we've decided to prioritize the API integration feature for Q2. The design is ready.
Alice: Sounds good. Let's wrap up. Action items: Bob updates forecast by Friday, Carol sends pipeline data by Wednesday, Bob drafts job descriptions by Monday, Carol gets budget approval by Friday.
Bob: Got it. Thanks everyone.
Carol: Thanks, good meeting."""


# ============================================
# ANALYSIS PIPELINE TESTS
# ============================================

class TestAnalysisPipeline:
    """Test the full analysis pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_analyze_with_transcript(self, client, meeting_id):
        """Full pipeline: upload transcript → analyze → get results."""
        # Upload transcript
        resp = await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        assert resp.status_code == 201

        # Run analysis
        resp = await client.post(f"/api/meetings/{meeting_id}/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["summary"] is not None
        assert data["summary"]["summary_text"] is not None
        assert len(data["summary"]["summary_text"]) > 0
        assert data["llm_provider"] is not None

    @pytest.mark.asyncio
    async def test_analyze_returns_action_items(self, client, meeting_id):
        """Analysis should extract action items from the transcript."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/analyze")
        data = resp.json()
        assert data["status"] == "completed"
        assert len(data["action_items"]) > 0

        # Each action item should have required fields
        for item in data["action_items"]:
            assert item["task"] is not None
            assert len(item["task"]) > 0
            assert item["status"] == "pending"
            assert item["confirmed"] is False

    @pytest.mark.asyncio
    async def test_analyze_returns_decisions(self, client, meeting_id):
        """Analysis should extract decisions from the transcript."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/analyze")
        data = resp.json()
        assert data["summary"]["decisions"] is not None
        assert isinstance(data["summary"]["decisions"], list)

    @pytest.mark.asyncio
    async def test_analyze_returns_speakers(self, client, meeting_id):
        """Analysis should identify speakers from the transcript."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        resp = await client.post(f"/api/meetings/{meeting_id}/analyze")
        data = resp.json()
        speakers = data["summary"]["speakers"]
        assert len(speakers) > 0
        speaker_names = [s["name"] for s in speakers]
        assert "Alice" in speaker_names or "Bob" in speaker_names

    @pytest.mark.asyncio
    async def test_analyze_no_transcript_returns_409(self, client, meeting_id):
        """Analysis without a transcript should return 409."""
        resp = await client.post(f"/api/meetings/{meeting_id}/analyze")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_meeting_returns_404(self, client):
        """Analysis on non-existent meeting returns 404."""
        fake_id = str(uuid4())
        resp = await client.post(f"/api/meetings/{fake_id}/analyze")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_analyze_returns_cached_on_second_call(self, client, meeting_id):
        """Second analyze call returns cached results without re-analyzing."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        resp1 = await client.post(f"/api/meetings/{meeting_id}/analyze")
        resp2 = await client.post(f"/api/meetings/{meeting_id}/analyze")
        assert resp1.json()["summary"]["id"] == resp2.json()["summary"]["id"]

    @pytest.mark.asyncio
    async def test_reanalyze_generates_new_results(self, client, meeting_id):
        """Reanalyze flag should generate fresh results."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )

        resp1 = await client.post(f"/api/meetings/{meeting_id}/analyze")
        first_id = resp1.json()["summary"]["id"]

        resp2 = await client.post(
            f"/api/meetings/{meeting_id}/analyze",
            json={"reanalyze": True},
        )
        assert resp2.json()["summary"]["id"] != first_id


# ============================================
# SUMMARY RETRIEVAL TESTS
# ============================================

class TestSummaryRetrieval:
    """Test summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_summary(self, client, meeting_id):
        """Get summary after analysis."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/analyze")

        resp = await client.get(f"/api/meetings/{meeting_id}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary_text"] is not None
        assert data["meeting_id"] == meeting_id

    @pytest.mark.asyncio
    async def test_get_summary_before_analysis_returns_404(self, client, meeting_id):
        """Summary endpoint returns 404 if not analyzed yet."""
        resp = await client.get(f"/api/meetings/{meeting_id}/summary")
        assert resp.status_code == 404


# ============================================
# ACTION ITEM TESTS
# ============================================

class TestActionItems:
    """Test action item listing and management."""

    @pytest.mark.asyncio
    async def test_list_action_items(self, client, meeting_id):
        """List action items after analysis."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/analyze")

        resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) > 0
        assert all(item["confirmed"] is False for item in items)

    @pytest.mark.asyncio
    async def test_confirm_action_item(self, client, meeting_id):
        """Confirm an AI-extracted action item."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/analyze")

        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        item_id = items_resp.json()[0]["id"]

        resp = await client.patch(
            f"/api/action-items/{item_id}",
            json={"confirmed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["confirmed"] is True
        assert resp.json()["confirmed_at"] is not None

    @pytest.mark.asyncio
    async def test_update_action_item_status(self, client, meeting_id):
        """Change action item status to in_progress then completed."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/analyze")

        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        item_id = items_resp.json()[0]["id"]

        # Move to in_progress
        resp = await client.patch(
            f"/api/action-items/{item_id}",
            json={"status": "in_progress"},
        )
        assert resp.json()["status"] == "in_progress"

        # Complete it
        resp = await client.patch(
            f"/api/action-items/{item_id}",
            json={"status": "completed"},
        )
        assert resp.json()["status"] == "completed"
        assert resp.json()["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_update_action_item_priority(self, client, meeting_id):
        """Change action item priority."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_TRANSCRIPT},
        )
        await client.post(f"/api/meetings/{meeting_id}/analyze")

        items_resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        item_id = items_resp.json()[0]["id"]

        resp = await client.patch(
            f"/api/action-items/{item_id}",
            json={"priority": "high"},
        )
        assert resp.json()["priority"] == "high"

    @pytest.mark.asyncio
    async def test_update_nonexistent_action_item(self, client):
        """Updating non-existent action item returns 404."""
        fake_id = str(uuid4())
        resp = await client.patch(
            f"/api/action-items/{fake_id}",
            json={"confirmed": True},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_action_items_list(self, client, meeting_id):
        """List returns empty array when no analysis has been run."""
        resp = await client.get(f"/api/meetings/{meeting_id}/action-items")
        assert resp.status_code == 200
        assert resp.json() == []
