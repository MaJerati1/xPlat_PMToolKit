"""SQLAlchemy ORM models for the Transcript Ingestion module.

Covers: transcripts and transcript_segments tables.
Based on the data model defined in System Architecture Document v1.0, Section 5.
"""

import uuid
import datetime as dt
from typing import Optional, List

from sqlalchemy import (
    String, Text, Integer, Float, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.types import GUID


class Transcript(Base):
    """Uploaded transcript record with parsing status tracking."""
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    original_format: Mapped[str] = mapped_column(String(20), default="txt")
    original_filename: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    parsed_status: Mapped[str] = mapped_column(String(50), default="pending")
    parse_error: Mapped[Optional[str]] = mapped_column(Text)
    segment_count: Mapped[int] = mapped_column(Integer, default=0)
    speaker_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    uploaded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    parsed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    segments: Mapped[List["TranscriptSegment"]] = relationship(
        back_populates="transcript", lazy="selectin",
        order_by="TranscriptSegment.segment_order",
        cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    """Individual parsed transcript segment (one speaker turn)."""
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    segment_order: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_id: Mapped[Optional[str]] = mapped_column(String(255))
    speaker_name: Mapped[Optional[str]] = mapped_column(String(255))
    start_time: Mapped[Optional[float]] = mapped_column(Float)
    end_time: Mapped[Optional[float]] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    agenda_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="SET NULL")
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    transcript: Mapped["Transcript"] = relationship(back_populates="segments")
