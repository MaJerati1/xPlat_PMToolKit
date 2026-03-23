"""Transcript Service - business logic for transcript upload, parsing, and retrieval.

Handles file upload processing, format detection, parser dispatch,
segment storage, and transcript metadata management.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transcript import Transcript, TranscriptSegment
from app.models.meeting import Meeting
from app.schemas.transcript import (
    TranscriptUploadResponse, TranscriptStatusResponse,
    TranscriptSegmentsResponse, SegmentResponse,
    TranscriptFormat, ParsedSegment,
)
from app.parsers.transcript_parser import parse_transcript


class TranscriptService:
    """Service layer for transcript-related business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_meeting_or_none(self, meeting_id: uuid.UUID) -> Optional[Meeting]:
        """Verify a meeting exists."""
        result = await self.db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def get_transcript(self, meeting_id: uuid.UUID) -> Optional[Transcript]:
        """Get the transcript for a meeting (1:1 relationship)."""
        result = await self.db.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def upload_and_parse(
        self,
        meeting_id: uuid.UUID,
        raw_text: str,
        filename: Optional[str] = None,
        file_size: Optional[int] = None,
        format_hint: Optional[TranscriptFormat] = None,
    ) -> Transcript:
        """Upload raw transcript text, parse it, and store segments.

        This is the core ingestion pipeline:
          1. Create or replace transcript record
          2. Auto-detect format (or use hint)
          3. Run format-specific parser
          4. Store normalized segments
          5. Update metadata (segment count, speaker count, duration)

        Args:
            meeting_id: Meeting to attach transcript to.
            raw_text: Raw transcript content.
            filename: Original filename (helps format detection).
            file_size: File size in bytes (for metadata).
            format_hint: Explicit format (skips auto-detection).

        Returns:
            The created/updated Transcript ORM object.
        """
        # Check if transcript already exists for this meeting (replace it)
        existing = await self.get_transcript(meeting_id)
        if existing:
            # Delete existing transcript and segments (cascade)
            await self.db.delete(existing)
            await self.db.flush()

        # Create transcript record
        transcript = Transcript(
            meeting_id=meeting_id,
            raw_text=raw_text,
            original_filename=filename,
            file_size_bytes=file_size or len(raw_text.encode("utf-8")),
            parsed_status="parsing",
        )
        self.db.add(transcript)
        await self.db.flush()

        # Parse the transcript
        try:
            result = parse_transcript(raw_text, filename=filename, format_hint=format_hint)

            if result.errors and not result.segments:
                # Parsing failed entirely
                transcript.parsed_status = "failed"
                transcript.parse_error = "; ".join(result.errors)
                transcript.original_format = result.format_detected.value
                await self.db.flush()
                await self.db.refresh(transcript)
                return transcript

            # Store segments
            for i, seg in enumerate(result.segments):
                db_segment = TranscriptSegment(
                    transcript_id=transcript.id,
                    segment_order=i,
                    speaker_id=seg.speaker_id,
                    speaker_name=seg.speaker_name,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    text=seg.text,
                )
                self.db.add(db_segment)

            # Update transcript metadata
            transcript.original_format = result.format_detected.value
            transcript.parsed_status = "parsed"
            transcript.segment_count = len(result.segments)
            transcript.speaker_count = len(result.speaker_names)
            transcript.duration_seconds = result.duration_seconds
            transcript.parsed_at = datetime.now(timezone.utc)

            if result.errors:
                transcript.parse_error = "; ".join(result.errors)

            await self.db.flush()
            await self.db.refresh(transcript)
            return transcript

        except Exception as e:
            transcript.parsed_status = "failed"
            transcript.parse_error = str(e)
            await self.db.flush()
            await self.db.refresh(transcript)
            return transcript

    async def delete_transcript(self, meeting_id: uuid.UUID) -> bool:
        """Delete a transcript and all its segments."""
        transcript = await self.get_transcript(meeting_id)
        if not transcript:
            return False
        await self.db.delete(transcript)
        await self.db.flush()
        return True

    # ============================================
    # RESPONSE BUILDERS
    # ============================================

    def build_upload_response(self, transcript: Transcript) -> TranscriptUploadResponse:
        """Build the upload response from ORM object."""
        return TranscriptUploadResponse.model_validate(transcript)

    def build_status_response(self, transcript: Transcript) -> TranscriptStatusResponse:
        """Build the status response from ORM object."""
        return TranscriptStatusResponse.model_validate(transcript)

    def build_segments_response(
        self, transcript: Transcript, meeting_id: uuid.UUID
    ) -> TranscriptSegmentsResponse:
        """Build the full segments response with speaker list."""
        speakers = sorted(set(
            s.speaker_name for s in transcript.segments
            if s.speaker_name
        ))

        return TranscriptSegmentsResponse(
            transcript_id=transcript.id,
            meeting_id=meeting_id,
            original_format=transcript.original_format,
            parsed_status=transcript.parsed_status,
            segment_count=transcript.segment_count,
            speaker_count=transcript.speaker_count,
            duration_seconds=transcript.duration_seconds,
            speakers=speakers,
            segments=[SegmentResponse.model_validate(s) for s in transcript.segments],
        )
