"""SQLAlchemy ORM models for the After Meeting module.

Covers: meeting_summaries and action_items tables.
Based on the data model defined in System Architecture Document v1.0, Section 5.
"""

import uuid
import datetime as dt
from typing import Optional, List

from sqlalchemy import (
    String, Text, Integer, Boolean, Date, DateTime, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.types import GUID


class MeetingSummary(Base):
    """LLM-generated meeting summary with structured analysis outputs."""
    __tablename__ = "meeting_summaries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    summary_text: Mapped[Optional[str]] = mapped_column(Text)
    decisions_json: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    topics_json: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    speakers_json: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50))
    llm_model: Mapped[Optional[str]] = mapped_column(String(100))
    llm_tier: Mapped[Optional[int]] = mapped_column(Integer)
    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ActionItem(Base):
    """Action item extracted from transcript by LLM, pending user confirmation."""
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    task: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    owner_name: Mapped[Optional[str]] = mapped_column(String(255))
    deadline: Mapped[Optional[dt.date]] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    source_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("transcript_segments.id", ondelete="SET NULL")
    )
    source_quote: Mapped[Optional[str]] = mapped_column(Text)
    dependencies: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    reminder_sent_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
