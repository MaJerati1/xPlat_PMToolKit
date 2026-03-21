"""Pydantic schemas for the Transcript Ingestion module.

Defines request/response models for transcript upload, parsing status,
segments, and speaker data.
"""

import uuid
import datetime as dt
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================
# ENUMS
# ============================================

class TranscriptFormat(str, Enum):
    txt = "txt"
    srt = "srt"
    vtt = "vtt"
    csv = "csv"
    json = "json"


class ParseStatus(str, Enum):
    pending = "pending"
    parsing = "parsing"
    parsed = "parsed"
    failed = "failed"


# ============================================
# SEGMENT SCHEMAS
# ============================================

class SegmentBase(BaseModel):
    """Base segment data produced by parsers."""
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = None
    start_time: Optional[float] = Field(None, description="Start time in seconds")
    end_time: Optional[float] = Field(None, description="End time in seconds")
    text: str = Field(..., min_length=1)


class SegmentResponse(SegmentBase):
    """Segment as returned from the API."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transcript_id: uuid.UUID
    segment_order: int
    agenda_item_id: Optional[uuid.UUID] = None
    created_at: dt.datetime


# ============================================
# TRANSCRIPT SCHEMAS
# ============================================

class TranscriptUploadResponse(BaseModel):
    """Response after uploading a transcript."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    original_format: str
    original_filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    parsed_status: str
    segment_count: int
    speaker_count: int
    duration_seconds: Optional[int] = None
    uploaded_at: dt.datetime
    parsed_at: Optional[dt.datetime] = None


class TranscriptStatusResponse(BaseModel):
    """Transcript processing status."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    original_format: str
    original_filename: Optional[str] = None
    parsed_status: str
    parse_error: Optional[str] = None
    segment_count: int
    speaker_count: int
    duration_seconds: Optional[int] = None
    uploaded_at: dt.datetime
    parsed_at: Optional[dt.datetime] = None


class TranscriptSegmentsResponse(BaseModel):
    """Full transcript segments with metadata."""
    transcript_id: uuid.UUID
    meeting_id: uuid.UUID
    original_format: str
    parsed_status: str
    segment_count: int
    speaker_count: int
    duration_seconds: Optional[int] = None
    speakers: List[str] = Field(default_factory=list, description="Unique speaker names found")
    segments: List[SegmentResponse] = []


class TranscriptTextSubmit(BaseModel):
    """Schema for submitting transcript as pasted text (JSON body alternative to form)."""
    text: str = Field(..., min_length=1, max_length=500000, description="Raw transcript text")
    format_hint: Optional[TranscriptFormat] = Field(
        None, description="Optional format hint (auto-detected if omitted)"
    )

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        """Reject whitespace-only text."""
        if not v.strip():
            raise ValueError("Transcript text cannot be blank")
        return v


# ============================================
# PARSED OUTPUT (internal, used by parsers)
# ============================================

class ParsedSegment(BaseModel):
    """Internal model for parser output before DB insertion."""
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    text: str


class ParseResult(BaseModel):
    """Complete parser output."""
    segments: List[ParsedSegment]
    format_detected: TranscriptFormat
    duration_seconds: Optional[int] = None
    speaker_names: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
