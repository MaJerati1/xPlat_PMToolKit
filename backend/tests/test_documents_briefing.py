"""Tests for document gathering engine and briefing package generator.

Tests cover:
  - Document suggestion endpoint (with and without Google token)
  - Document approval workflow
  - Document listing and removal
  - Briefing generation (JSON and docx formats)
  - Outstanding action items in briefing
"""

import pytest
from httpx import AsyncClient


# ============================================
# DOCUMENT SUGGESTION
# ============================================

@pytest.mark.asyncio
async def test_suggest_documents_no_token(client: AsyncClient, sample_meeting_id: str):
    """Suggest endpoint returns graceful message when no Google token is provided."""
    resp = await client.get(f"/api/meetings/{sample_meeting_id}/documents/suggest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggestions"] == []
    assert "Google" in data["message"] or "agenda" in data["message"].lower()


@pytest.mark.asyncio
async def test_suggest_documents_no_agenda(client: AsyncClient):
    """Suggest endpoint returns message when meeting has no agenda items."""
    # Create a meeting with no agenda
    resp = await client.post("/api/meetings", json={"title": "Empty meeting"})
    mid = resp.json()["id"]

    resp = await client.get(f"/api/meetings/{mid}/documents/suggest")
    assert resp.status_code == 200
    data = resp.json()
    assert "agenda" in data["message"].lower()


@pytest.mark.asyncio
async def test_suggest_documents_missing_meeting(client: AsyncClient):
    """Suggest endpoint returns 404 for non-existent meeting."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/meetings/{fake_id}/documents/suggest")
    assert resp.status_code == 404


# ============================================
# DOCUMENT APPROVAL
# ============================================

@pytest.mark.asyncio
async def test_approve_documents_empty(client: AsyncClient, sample_meeting_id: str):
    """Approving empty list returns zero count."""
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/documents/approve",
        json={"approved_file_ids": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved_count"] == 0


@pytest.mark.asyncio
async def test_approve_documents_creates_records(client: AsyncClient, sample_meeting_id: str):
    """Approving file IDs creates document records."""
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/documents/approve",
        json={"approved_file_ids": ["file_abc123", "file_def456"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved_count"] == 2
    assert len(data["documents"]) == 2
    assert data["documents"][0]["approved"] is True


@pytest.mark.asyncio
async def test_approve_documents_no_duplicates(client: AsyncClient, sample_meeting_id: str):
    """Approving the same file ID twice doesn't create duplicates."""
    # First approval
    await client.post(
        f"/api/meetings/{sample_meeting_id}/documents/approve",
        json={"approved_file_ids": ["file_unique_001"]},
    )
    # Second approval of same file
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/documents/approve",
        json={"approved_file_ids": ["file_unique_001"]},
    )
    data = resp.json()
    assert data["approved_count"] == 0  # No new docs created


@pytest.mark.asyncio
async def test_approve_documents_missing_meeting(client: AsyncClient):
    """Approve returns 404 for non-existent meeting."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/meetings/{fake_id}/documents/approve",
        json={"approved_file_ids": ["file_123"]},
    )
    assert resp.status_code == 404


# ============================================
# DOCUMENT LISTING AND REMOVAL
# ============================================

@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient, sample_meeting_id: str):
    """List documents for a meeting."""
    # Add some documents first
    await client.post(
        f"/api/meetings/{sample_meeting_id}/documents/approve",
        json={"approved_file_ids": ["file_list_1", "file_list_2"]},
    )

    resp = await client.get(f"/api/meetings/{sample_meeting_id}/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_list_documents_approved_only(client: AsyncClient, sample_meeting_id: str):
    """Filter to approved documents only."""
    resp = await client.get(
        f"/api/meetings/{sample_meeting_id}/documents?approved_only=true"
    )
    assert resp.status_code == 200
    for doc in resp.json()["documents"]:
        assert doc["approved"] is True


@pytest.mark.asyncio
async def test_remove_document(client: AsyncClient, sample_meeting_id: str):
    """Remove a document from a meeting."""
    # Add a document
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/documents/approve",
        json={"approved_file_ids": ["file_to_remove"]},
    )
    doc_id = resp.json()["documents"][0]["id"]

    # Remove it
    resp = await client.delete(
        f"/api/meetings/{sample_meeting_id}/documents/{doc_id}"
    )
    assert resp.status_code == 204


# ============================================
# BRIEFING GENERATION
# ============================================

@pytest.mark.asyncio
async def test_briefing_json(client: AsyncClient, sample_meeting_id: str):
    """Generate briefing in JSON format."""
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/briefing",
        json={"format": "json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meeting_id"] == sample_meeting_id
    assert "sections" in data
    assert len(data["sections"]) >= 1  # At least meeting overview


@pytest.mark.asyncio
async def test_briefing_includes_agenda(client: AsyncClient, sample_meeting_id: str):
    """Briefing includes agenda section when agenda items exist."""
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/briefing",
        json={"format": "json"},
    )
    data = resp.json()
    section_titles = [s["title"] for s in data["sections"]]
    assert "Agenda" in section_titles


@pytest.mark.asyncio
async def test_briefing_metadata(client: AsyncClient, sample_meeting_id: str):
    """Briefing includes metadata counts."""
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/briefing",
        json={"format": "json"},
    )
    data = resp.json()
    assert "metadata" in data
    assert "agenda_items_count" in data["metadata"]


@pytest.mark.asyncio
async def test_briefing_docx(client: AsyncClient, sample_meeting_id: str):
    """Generate briefing as Word document."""
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/briefing",
        json={"format": "docx"},
    )
    assert resp.status_code == 200
    assert "openxmlformats" in resp.headers.get("content-type", "")
    assert len(resp.content) > 100  # Should be a real docx file


@pytest.mark.asyncio
async def test_briefing_missing_meeting(client: AsyncClient):
    """Briefing returns 404 for non-existent meeting."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/meetings/{fake_id}/briefing",
        json={"format": "json"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_briefing_without_optional_sections(client: AsyncClient, sample_meeting_id: str):
    """Briefing can exclude optional sections."""
    resp = await client.post(
        f"/api/meetings/{sample_meeting_id}/briefing",
        json={
            "format": "json",
            "include_outstanding_actions": False,
            "include_documents": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    section_titles = [s["title"] for s in data["sections"]]
    assert "Outstanding Action Items" not in section_titles
    assert "Reference Documents" not in section_titles
