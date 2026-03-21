"""SQLAlchemy ORM models for the Before Meeting module.

Covers: meetings, agenda_items, meeting_attendees, and documents tables.
Based on the data model defined in System Architecture Document v1.0, Section 5.
"""

import uuid
from datetime import date, time, datetime
from typing import Optional, List

from sqlalchemy import (
    String, Text, Integer, Boolean, Float, Date, Time,
    DateTime, ForeignKey, UniqueConstraint, CheckConstraint, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.types import GUID


class Organization(Base):
    """Organization/workspace that owns meetings and configures LLM isolation tier."""
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    llm_tier_default: Mapped[int] = mapped_column(Integer, default=1)
    settings_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="organization", lazy="selectin")
    meetings: Mapped[List["Meeting"]] = relationship(back_populates="organization", lazy="selectin")


class User(Base):
    """User account with organization membership."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(50), default="auth0")
    auth_provider_id: Mapped[Optional[str]] = mapped_column(String(255))
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="users")
    organized_meetings: Mapped[List["Meeting"]] = relationship(back_populates="organizer", lazy="selectin")


class Meeting(Base):
    """Core meeting record linking all modules together."""
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    date: Mapped[Optional[date]] = mapped_column(Date)
    time: Mapped[Optional[time]] = mapped_column(Time)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    organizer_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"))
    calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255))
    calendar_provider: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    llm_tier: Mapped[Optional[int]] = mapped_column(Integer)
    meeting_link: Mapped[Optional[str]] = mapped_column(String(1000))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organizer: Mapped[Optional["User"]] = relationship(back_populates="organized_meetings")
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="meetings")
    agenda_items: Mapped[List["AgendaItem"]] = relationship(
        back_populates="meeting", lazy="selectin", order_by="AgendaItem.item_order",
        cascade="all, delete-orphan"
    )
    attendees: Mapped[List["MeetingAttendee"]] = relationship(
        back_populates="meeting", lazy="selectin",
        cascade="all, delete-orphan"
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="meeting", lazy="selectin",
        cascade="all, delete-orphan"
    )


class AgendaItem(Base):
    """Individual agenda topic for a meeting."""
    __tablename__ = "agenda_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    time_allocation_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    item_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    presenter_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    meeting: Mapped["Meeting"] = relationship(back_populates="agenda_items")
    presenter: Mapped[Optional["User"]] = relationship(lazy="selectin")


class MeetingAttendee(Base):
    """Meeting attendee with role assignment."""
    __tablename__ = "meeting_attendees"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="attendee")
    rsvp_status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("meeting_id", "email", name="uq_meeting_attendee_email"),)

    # Relationships
    meeting: Mapped["Meeting"] = relationship(back_populates="attendees")
    user: Mapped[Optional["User"]] = relationship(lazy="selectin")


class Document(Base):
    """Documents gathered and approved for briefing packages."""
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    agenda_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(50), default="google_drive")
    source_file_id: Mapped[Optional[str]] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    file_url: Mapped[Optional[str]] = mapped_column(String(2000))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    meeting: Mapped["Meeting"] = relationship(back_populates="documents")
    agenda_item: Mapped[Optional["AgendaItem"]] = relationship(lazy="selectin")
