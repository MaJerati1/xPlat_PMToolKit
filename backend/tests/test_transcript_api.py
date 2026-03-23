"""Integration tests for Transcript Ingestion API endpoints.

Tests transcript upload (form + JSON body), status check, segment retrieval,
deletion, and error handling. Database setup and client fixtures provided by conftest.py.
"""

import pytest
from uuid import uuid4


# ============================================
# SAMPLE TRANSCRIPTS
# ============================================

SAMPLE_SRT = """1
00:00:01,000 --> 00:00:04,500
Alice: Good morning everyone.

2
00:00:05,000 --> 00:00:08,200
Bob: Thanks for joining.

3
00:00:09,000 --> 00:00:15,000
Alice: Let's review the agenda.
"""

SAMPLE_VTT = """WEBVTT

00:00:01.000 --> 00:00:04.500
<v Alice>Good morning everyone.</v>

00:00:05.000 --> 00:00:08.200
<v Bob>Thanks for joining.</v>
"""

SAMPLE_PLAIN = """Alice: Good morning everyone.
Bob: Thanks Alice, let's begin.
Alice: First, the revenue review.
Carol: I have those numbers ready.
"""

SAMPLE_JSON = """[
    {"speaker": "Alice", "text": "Good morning.", "start_time": 0, "end_time": 4.5},
    {"speaker": "Bob", "text": "Hello everyone.", "start_time": 5, "end_time": 8}
]"""


# ============================================
# UPLOAD TESTS
# ============================================

class TestTranscriptUpload:
    """Test transcript upload and parsing."""

    @pytest.mark.asyncio
    async def test_upload_text_via_json(self, client, meeting_id):
        """Upload transcript as JSON body."""
        resp = await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_PLAIN},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parsed_status"] == "parsed"
        assert data["segment_count"] == 4
        assert data["speaker_count"] >= 2
        assert data["original_format"] == "txt"

    @pytest.mark.asyncio
    async def test_upload_srt_via_json(self, client, meeting_id):
        """Upload SRT content with format hint."""
        resp = await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_SRT, "format_hint": "srt"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parsed_status"] == "parsed"
        assert data["segment_count"] == 3
        assert data["original_format"] == "srt"
        assert data["duration_seconds"] == 15

    @pytest.mark.asyncio
    async def test_upload_json_format(self, client, meeting_id):
        """Upload JSON transcript."""
        resp = await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_JSON, "format_hint": "json"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parsed_status"] == "parsed"
        assert data["segment_count"] == 2

    @pytest.mark.asyncio
    async def test_upload_replaces_existing(self, client, meeting_id):
        """Uploading a second transcript replaces the first."""
        resp1 = await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_PLAIN},
        )
        assert resp1.json()["segment_count"] == 4

        resp2 = await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_JSON, "format_hint": "json"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["segment_count"] == 2
        assert resp2.json()["original_format"] == "json"

    @pytest.mark.asyncio
    async def test_upload_empty_text_rejected(self, client, meeting_id):
        """Empty text should be rejected."""
        resp = await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": "   "},
        )
        # Pydantic min_length=1 validation should catch this
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_nonexistent_meeting(self, client):
        """Upload to non-existent meeting returns 404."""
        fake_id = str(uuid4())
        resp = await client.post(
            f"/api/meetings/{fake_id}/transcript/text",
            json={"text": "Hello world."},
        )
        assert resp.status_code == 404


# ============================================
# STATUS TESTS
# ============================================

class TestTranscriptStatus:
    """Test transcript status retrieval."""

    @pytest.mark.asyncio
    async def test_get_status_after_upload(self, client, meeting_id):
        """Status should be 'parsed' after successful upload."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_PLAIN},
        )

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parsed_status"] == "parsed"
        assert data["segment_count"] == 4

    @pytest.mark.asyncio
    async def test_status_no_transcript(self, client, meeting_id):
        """Status returns 404 if no transcript uploaded."""
        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/status")
        assert resp.status_code == 404


# ============================================
# SEGMENT RETRIEVAL TESTS
# ============================================

class TestTranscriptSegments:
    """Test segment retrieval."""

    @pytest.mark.asyncio
    async def test_get_segments(self, client, meeting_id):
        """Retrieve all segments after upload."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_SRT, "format_hint": "srt"},
        )

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/segments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment_count"] == 3
        assert len(data["segments"]) == 3
        assert data["segments"][0]["text"] == "Good morning everyone."
        assert "Alice" in data["speakers"]
        assert "Bob" in data["speakers"]
        assert data["duration_seconds"] == 15

    @pytest.mark.asyncio
    async def test_segments_ordered(self, client, meeting_id):
        """Segments should be returned in order."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_PLAIN},
        )

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/segments")
        segments = resp.json()["segments"]
        orders = [s["segment_order"] for s in segments]
        assert orders == sorted(orders)

    @pytest.mark.asyncio
    async def test_segments_no_transcript(self, client, meeting_id):
        """Segments returns 404 if no transcript."""
        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/segments")
        assert resp.status_code == 404


# ============================================
# DELETE TESTS
# ============================================

class TestTranscriptDelete:
    """Test transcript deletion."""

    @pytest.mark.asyncio
    async def test_delete_transcript(self, client, meeting_id):
        """Delete transcript and verify it's gone."""
        await client.post(
            f"/api/meetings/{meeting_id}/transcript/text",
            json={"text": SAMPLE_PLAIN},
        )

        resp = await client.delete(f"/api/meetings/{meeting_id}/transcript")
        assert resp.status_code == 204

        resp = await client.get(f"/api/meetings/{meeting_id}/transcript/status")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client, meeting_id):
        """Delete when no transcript exists returns 404."""
        resp = await client.delete(f"/api/meetings/{meeting_id}/transcript")
        assert resp.status_code == 404
