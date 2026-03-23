"""Pydantic schemas for the Before Meeting module.

Defines request/response models for meetings, agenda items, attendees, and documents.
"""

import uuid
import datetime as dt
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================
# ENUMS
# ============================================

class MeetingStatus(str, Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class AgendaItemStatus(str, Enum):
    pending = "pending"
    discussed = "discussed"
    deferred = "deferred"
    skipped = "skipped"


class AttendeeRole(str, Enum):
    organizer = "organizer"
    facilitator = "facilitator"
    note_taker = "note_taker"
    decision_maker = "decision_maker"
    attendee = "attendee"


class RSVPStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    tentative = "tentative"


class DocumentSource(str, Enum):
    google_drive = "google_drive"
    onedrive = "onedrive"
    upload = "upload"
    manual = "manual"


# ============================================
# AGENDA ITEM SCHEMAS
# ============================================

class AgendaItemCreate(BaseModel):
    """Schema for creating a single agenda item."""
    title: str = Field(..., min_length=1, max_length=500, description="Agenda item title")
    description: Optional[str] = Field(None, description="Detailed description or talking points")
    time_allocation_minutes: Optional[int] = Field(None, ge=1, le=480, description="Minutes allocated")
    item_order: Optional[int] = Field(None, ge=0, description="Position in agenda (auto-assigned if omitted)")
    presenter_id: Optional[uuid.UUID] = Field(None, description="User ID of the presenter")


class AgendaItemUpdate(BaseModel):
    """Schema for updating an existing agenda item."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    time_allocation_minutes: Optional[int] = Field(None, ge=1, le=480)
    item_order: Optional[int] = Field(None, ge=0)
    status: Optional[AgendaItemStatus] = None
    presenter_id: Optional[uuid.UUID] = None


class AgendaItemResponse(BaseModel):
    """Schema for returning an agenda item."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    title: str
    description: Optional[str] = None
    time_allocation_minutes: Optional[int] = None
    item_order: int
    status: str
    presenter_id: Optional[uuid.UUID] = None
    created_at: dt.datetime


class AgendaItemReorder(BaseModel):
    """Schema for reordering agenda items."""
    item_ids: List[uuid.UUID] = Field(
        ..., min_length=1,
        description="Ordered list of agenda item IDs representing the new order"
    )


# ============================================
# ATTENDEE SCHEMAS
# ============================================

class AttendeeCreate(BaseModel):
    """Schema for adding an attendee to a meeting."""
    email: str = Field(..., description="Attendee email address")
    name: Optional[str] = Field(None, max_length=255, description="Attendee display name")
    role: AttendeeRole = Field(AttendeeRole.attendee, description="Role in the meeting")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format without using EmailStr (avoids Pydantic v2.10 recursion bug)."""
        import re
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email address")
        return v.lower().strip()


class AttendeeResponse(BaseModel):
    """Schema for returning an attendee."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    email: Optional[str] = None
    name: Optional[str] = None
    role: str
    rsvp_status: str
    created_at: dt.datetime


# ============================================
# MEETING SCHEMAS
# ============================================

class MeetingCreate(BaseModel):
    """Schema for creating a new meeting."""
    title: str = Field(..., min_length=1, max_length=500, description="Meeting title")
    date: Optional[dt.date] = Field(None, description="Meeting date (YYYY-MM-DD)")
    time: Optional[dt.time] = Field(None, description="Meeting start time (HH:MM)")
    duration_minutes: Optional[int] = Field(None, ge=5, le=480, description="Duration in minutes")
    meeting_link: Optional[str] = Field(None, max_length=1000, description="Video call URL")
    notes: Optional[str] = Field(None, description="Free-form notes about the meeting")
    calendar_event_id: Optional[str] = Field(None, description="External calendar event ID")
    calendar_provider: Optional[str] = Field(None, description="Calendar source (google, outlook)")
    agenda_items: Optional[List[AgendaItemCreate]] = Field(
        None, description="Agenda items to create with the meeting"
    )
    attendees: Optional[List[AttendeeCreate]] = Field(
        None, description="Attendees to add to the meeting"
    )


class MeetingUpdate(BaseModel):
    """Schema for updating an existing meeting."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    duration_minutes: Optional[int] = Field(None, ge=5, le=480)
    status: Optional[MeetingStatus] = None
    meeting_link: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = None


class MeetingResponse(BaseModel):
    """Schema for returning a meeting with its related data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    duration_minutes: Optional[int] = None
    organizer_id: Optional[uuid.UUID] = None
    org_id: Optional[uuid.UUID] = None
    calendar_event_id: Optional[str] = None
    calendar_provider: Optional[str] = None
    status: str
    llm_tier: Optional[int] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime
    agenda_items: List[AgendaItemResponse] = []
    attendees: List[AttendeeResponse] = []
    total_agenda_time: Optional[int] = None


class MeetingListResponse(BaseModel):
    """Schema for paginated meeting list."""
    meetings: List[MeetingResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============================================
# AGENDA TEXT PARSING
# ============================================

class AgendaTextParseRequest(BaseModel):
    """Schema for parsing agenda items from freeform text."""
    text: str = Field(
        ..., min_length=1, max_length=10000,
        description="Freeform agenda text to parse into structured items"
    )
    use_llm: bool = Field(
        False,
        description="Use LLM for intelligent parsing (falls back to rule-based if unavailable)"
    )


class AgendaTextParseResponse(BaseModel):
    """Schema for parsed agenda items from text."""
    items: List[AgendaItemCreate]
    parse_method: str = Field(description="Method used: 'rule_based' or 'llm'")
    raw_text: str = Field(description="Original input text")
