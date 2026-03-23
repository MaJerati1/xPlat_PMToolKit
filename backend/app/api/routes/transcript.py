"""Transcript Ingestion module API routes.

Fully implemented endpoints for:
  - Transcript upload (file or pasted text) with auto-format detection
  - Transcript upload via JSON body (alternative to multipart form)
  - Parsing status check
  - Segment retrieval with speaker listing
  - Transcript deletion and replacement
  - Agenda coverage analysis (stub for LLM task)
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.transcript import (
    TranscriptUploadResponse, TranscriptStatusResponse,
    TranscriptSegmentsResponse, TranscriptTextSubmit, TranscriptFormat,
)
from app.services.transcript_service import TranscriptService

router = APIRouter()


@router.post(
    "/meetings/{meeting_id}/transcript",
    response_model=TranscriptUploadResponse,
    status_code=201,
)
async def upload_transcript(
    meeting_id: UUID,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    format_hint: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a transcript file or paste text for parsing.

    Accepts multipart form data with either:
    - **file**: Upload an SRT, VTT, CSV, JSON, or TXT file
    - **text**: Paste raw transcript text directly

    Format is auto-detected from file extension and content heuristics.
    Optionally provide **format_hint** to override detection (srt, vtt, csv, json, txt).

    If a transcript already exists for this meeting, it will be replaced.
    """
    service = TranscriptService(db)

    meeting = await service.get_meeting_or_none(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not file and not text:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file upload or pasted text"
        )

    # Read file content if uploaded
    raw_text = text
    filename = None
    file_size = None

    if file:
        content_bytes = await file.read()
        raw_text = content_bytes.decode("utf-8", errors="replace")
        filename = file.filename
        file_size = len(content_bytes)

    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=400, detail="Transcript content is empty")

    # Parse format hint
    fmt_hint = None
    if format_hint:
        try:
            fmt_hint = TranscriptFormat(format_hint.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid format_hint: {format_hint}. Use: srt, vtt, csv, json, txt"
            )

    transcript = await service.upload_and_parse(
        meeting_id=meeting_id,
        raw_text=raw_text,
        filename=filename,
        file_size=file_size,
        format_hint=fmt_hint,
    )

    return service.build_upload_response(transcript)


@router.post(
    "/meetings/{meeting_id}/transcript/text",
    response_model=TranscriptUploadResponse,
    status_code=201,
)
async def upload_transcript_text(
    meeting_id: UUID,
    data: TranscriptTextSubmit,
    db: AsyncSession = Depends(get_db),
):
    """Upload transcript as JSON body (alternative to multipart form).

    Useful for programmatic submissions and pasted text from the frontend.

    Example:
    ```json
    {
      "text": "Alice: Good morning everyone...\\nBob: Thanks Alice...",
      "format_hint": "txt"
    }
    ```
    """
    service = TranscriptService(db)

    meeting = await service.get_meeting_or_none(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript = await service.upload_and_parse(
        meeting_id=meeting_id,
        raw_text=data.text,
        format_hint=data.format_hint,
    )

    return service.build_upload_response(transcript)


@router.get(
    "/meetings/{meeting_id}/transcript/status",
    response_model=TranscriptStatusResponse,
)
async def get_transcript_status(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check parsing/processing status of uploaded transcript.

    Returns the current status (pending, parsing, parsed, failed)
    along with metadata like segment count and any parse errors.
    """
    service = TranscriptService(db)

    meeting = await service.get_meeting_or_none(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript = await service.get_transcript(meeting_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="No transcript uploaded for this meeting")

    return service.build_status_response(transcript)


@router.get(
    "/meetings/{meeting_id}/transcript/segments",
    response_model=TranscriptSegmentsResponse,
)
async def get_transcript_segments(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve parsed and normalized transcript segments.

    Returns all segments ordered by position, along with metadata
    including unique speaker names, segment count, and duration.
    """
    service = TranscriptService(db)

    meeting = await service.get_meeting_or_none(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript = await service.get_transcript(meeting_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="No transcript uploaded for this meeting")

    if transcript.parsed_status != "parsed":
        raise HTTPException(
            status_code=409,
            detail=f"Transcript is not ready: status={transcript.parsed_status}"
        )

    return service.build_segments_response(transcript, meeting_id)


@router.delete("/meetings/{meeting_id}/transcript", status_code=204)
async def delete_transcript(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete the transcript and all parsed segments for a meeting."""
    service = TranscriptService(db)

    meeting = await service.get_meeting_or_none(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    deleted = await service.delete_transcript(meeting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No transcript found for this meeting")


@router.get("/meetings/{meeting_id}/transcript/coverage")
async def get_agenda_coverage(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get agenda coverage analysis.

    Maps transcript content to agenda items to show:
    - Which topics were discussed
    - Approximate time spent per topic
    - Which items were deferred or not covered

    Returns a coverage percentage and per-item breakdown.
    Requires both an agenda and a transcript to exist.
    """
    from app.services.continuity_service import ContinuityService
    service = ContinuityService(db)
    result = await service.analyze_coverage(meeting_id)
    return result
