"""Meeting Service - business logic for meetings, agenda items, and attendees.

Handles all CRUD operations and provides the bridge between API routes
and the database models. Uses async SQLAlchemy sessions.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from math import ceil

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import Meeting, AgendaItem, MeetingAttendee, Document
from app.schemas.meeting import (
    MeetingCreate, MeetingUpdate, MeetingResponse, MeetingListResponse,
    AgendaItemCreate, AgendaItemUpdate, AgendaItemResponse, AgendaItemReorder,
    AttendeeCreate, AttendeeResponse,
)


class MeetingService:
    """Service layer for meeting-related business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================
    # MEETING CRUD
    # ============================================

    async def create_meeting(self, data: MeetingCreate) -> Meeting:
        """Create a meeting with optional inline agenda items and attendees."""
        meeting = Meeting(
            title=data.title,
            date=data.date,
            time=data.time,
            duration_minutes=data.duration_minutes,
            meeting_link=data.meeting_link,
            notes=data.notes,
            calendar_event_id=data.calendar_event_id,
            calendar_provider=data.calendar_provider,
            status="scheduled",
        )
        self.db.add(meeting)
        await self.db.flush()  # Get the meeting ID before adding children

        # Add inline agenda items
        if data.agenda_items:
            for i, item_data in enumerate(data.agenda_items):
                agenda_item = AgendaItem(
                    meeting_id=meeting.id,
                    title=item_data.title,
                    description=item_data.description,
                    time_allocation_minutes=item_data.time_allocation_minutes,
                    item_order=item_data.item_order if item_data.item_order is not None else i,
                    presenter_id=item_data.presenter_id,
                )
                self.db.add(agenda_item)

        # Add inline attendees
        if data.attendees:
            for att_data in data.attendees:
                attendee = MeetingAttendee(
                    meeting_id=meeting.id,
                    email=att_data.email,
                    name=att_data.name,
                    role=att_data.role.value,
                )
                self.db.add(attendee)

        await self.db.flush()
        await self.db.refresh(meeting)
        return meeting

    async def get_meeting(self, meeting_id: uuid.UUID) -> Optional[Meeting]:
        """Get a meeting by ID with all relationships loaded."""
        result = await self.db.execute(
            select(Meeting)
            .options(
                selectinload(Meeting.agenda_items),
                selectinload(Meeting.attendees),
                selectinload(Meeting.documents),
            )
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def list_meetings(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Meeting], int]:
        """List meetings with pagination and optional filters.

        Returns:
            Tuple of (meetings_list, total_count)
        """
        query = select(Meeting).options(
            selectinload(Meeting.agenda_items),
            selectinload(Meeting.attendees),
        )
        count_query = select(func.count(Meeting.id))

        # Apply filters
        if status:
            query = query.where(Meeting.status == status)
            count_query = count_query.where(Meeting.status == status)
        if date_from:
            query = query.where(Meeting.date >= date_from)
            count_query = count_query.where(Meeting.date >= date_from)
        if date_to:
            query = query.where(Meeting.date <= date_to)
            count_query = count_query.where(Meeting.date <= date_to)
        if search:
            query = query.where(Meeting.title.ilike(f"%{search}%"))
            count_query = count_query.where(Meeting.title.ilike(f"%{search}%"))

        # Ordering and pagination
        query = query.order_by(Meeting.date.desc().nullslast(), Meeting.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        result = await self.db.execute(query)
        meetings = list(result.scalars().all())

        return meetings, total

    async def update_meeting(
        self, meeting_id: uuid.UUID, data: MeetingUpdate
    ) -> Optional[Meeting]:
        """Update meeting fields. Returns None if not found."""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if hasattr(value, "value"):  # Enum
                    setattr(meeting, field, value.value)
                else:
                    setattr(meeting, field, value)

        meeting.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(meeting)
        return meeting

    async def delete_meeting(self, meeting_id: uuid.UUID) -> bool:
        """Delete a meeting and all related data (cascade). Returns True if deleted."""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return False
        await self.db.delete(meeting)
        await self.db.flush()
        return True

    # ============================================
    # AGENDA ITEM CRUD
    # ============================================

    async def add_agenda_items(
        self, meeting_id: uuid.UUID, items: List[AgendaItemCreate]
    ) -> List[AgendaItem]:
        """Add multiple agenda items to a meeting."""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return []

        # Get the current max order
        existing_max = max((ai.item_order for ai in meeting.agenda_items), default=-1)

        created = []
        for i, item_data in enumerate(items):
            order = item_data.item_order if item_data.item_order is not None else (existing_max + 1 + i)
            agenda_item = AgendaItem(
                meeting_id=meeting_id,
                title=item_data.title,
                description=item_data.description,
                time_allocation_minutes=item_data.time_allocation_minutes,
                item_order=order,
                presenter_id=item_data.presenter_id,
            )
            self.db.add(agenda_item)
            created.append(agenda_item)

        await self.db.flush()
        for item in created:
            await self.db.refresh(item)
        return created

    async def get_agenda_items(self, meeting_id: uuid.UUID) -> List[AgendaItem]:
        """Get all agenda items for a meeting, ordered by item_order."""
        result = await self.db.execute(
            select(AgendaItem)
            .where(AgendaItem.meeting_id == meeting_id)
            .order_by(AgendaItem.item_order)
        )
        return list(result.scalars().all())

    async def update_agenda_item(
        self, item_id: uuid.UUID, data: AgendaItemUpdate
    ) -> Optional[AgendaItem]:
        """Update a single agenda item."""
        result = await self.db.execute(
            select(AgendaItem).where(AgendaItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if hasattr(value, "value"):
                    setattr(item, field, value.value)
                else:
                    setattr(item, field, value)

        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def delete_agenda_item(self, item_id: uuid.UUID) -> bool:
        """Delete a single agenda item."""
        result = await self.db.execute(
            select(AgendaItem).where(AgendaItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return False
        await self.db.delete(item)
        await self.db.flush()
        return True

    async def reorder_agenda_items(
        self, meeting_id: uuid.UUID, reorder: AgendaItemReorder
    ) -> List[AgendaItem]:
        """Reorder agenda items based on provided ID list."""
        items = await self.get_agenda_items(meeting_id)
        item_map = {item.id: item for item in items}

        for new_order, item_id in enumerate(reorder.item_ids):
            if item_id in item_map:
                item_map[item_id].item_order = new_order

        await self.db.flush()
        return await self.get_agenda_items(meeting_id)

    # ============================================
    # ATTENDEE CRUD
    # ============================================

    async def add_attendees(
        self, meeting_id: uuid.UUID, attendees: List[AttendeeCreate]
    ) -> List[MeetingAttendee]:
        """Add attendees to a meeting. Skips duplicates by email."""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return []

        existing_emails = {a.email for a in meeting.attendees if a.email}
        created = []

        for att_data in attendees:
            if att_data.email in existing_emails:
                continue  # Skip duplicates
            attendee = MeetingAttendee(
                meeting_id=meeting_id,
                email=att_data.email,
                name=att_data.name,
                role=att_data.role.value,
            )
            self.db.add(attendee)
            created.append(attendee)
            existing_emails.add(att_data.email)

        await self.db.flush()
        for att in created:
            await self.db.refresh(att)
        return created

    async def get_attendees(self, meeting_id: uuid.UUID) -> List[MeetingAttendee]:
        """Get all attendees for a meeting."""
        result = await self.db.execute(
            select(MeetingAttendee)
            .where(MeetingAttendee.meeting_id == meeting_id)
            .order_by(MeetingAttendee.created_at)
        )
        return list(result.scalars().all())

    async def remove_attendee(self, attendee_id: uuid.UUID) -> bool:
        """Remove an attendee from a meeting."""
        result = await self.db.execute(
            select(MeetingAttendee).where(MeetingAttendee.id == attendee_id)
        )
        attendee = result.scalar_one_or_none()
        if not attendee:
            return False
        await self.db.delete(attendee)
        await self.db.flush()
        return True

    # ============================================
    # HELPERS
    # ============================================

    def build_meeting_response(self, meeting: Meeting) -> MeetingResponse:
        """Convert ORM Meeting to response schema with computed fields."""
        total_time = sum(
            ai.time_allocation_minutes
            for ai in meeting.agenda_items
            if ai.time_allocation_minutes
        ) or None

        return MeetingResponse(
            id=meeting.id,
            title=meeting.title,
            date=meeting.date,
            time=meeting.time,
            duration_minutes=meeting.duration_minutes,
            organizer_id=meeting.organizer_id,
            org_id=meeting.org_id,
            calendar_event_id=meeting.calendar_event_id,
            calendar_provider=meeting.calendar_provider,
            status=meeting.status,
            llm_tier=meeting.llm_tier,
            meeting_link=meeting.meeting_link,
            notes=meeting.notes,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            agenda_items=[AgendaItemResponse.model_validate(ai) for ai in meeting.agenda_items],
            attendees=[AttendeeResponse.model_validate(a) for a in meeting.attendees],
            total_agenda_time=total_time,
        )

    def build_list_response(
        self, meetings: List[Meeting], total: int, page: int, per_page: int
    ) -> MeetingListResponse:
        """Build paginated list response."""
        return MeetingListResponse(
            meetings=[self.build_meeting_response(m) for m in meetings],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=ceil(total / per_page) if per_page > 0 else 0,
        )
