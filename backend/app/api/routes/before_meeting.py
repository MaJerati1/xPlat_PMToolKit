"""Before Meeting module API routes.

Fully implemented endpoints for:
  - Meeting CRUD (create, read, update, delete, list)
  - Agenda item CRUD (add, update, delete, reorder, parse from text)
  - Attendee management (add, list, remove)
  - Document suggestion and approval (stubs for future implementation)
  - Briefing package generation (stub for future implementation)
  - Calendar event import (stub for future implementation)
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.meeting import (
    MeetingCreate, MeetingUpdate, MeetingResponse, MeetingListResponse,
    AgendaItemCreate, AgendaItemUpdate, AgendaItemResponse, AgendaItemReorder,
    AttendeeCreate, AttendeeResponse,
    AgendaTextParseRequest, AgendaTextParseResponse,
)
from app.services.meeting_service import MeetingService
from app.parsers.agenda_parser import parse_agenda_text

router = APIRouter()


# ============================================
# MEETING ENDPOINTS
# ============================================

@router.post("/meetings", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    data: MeetingCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new meeting with optional inline agenda items and attendees.

    Accepts a meeting definition and optionally includes agenda_items and attendees
    arrays to create everything in a single request.

    Example request body:
    ```json
    {
      "title": "Q2 Planning Session",
      "date": "2026-04-01",
      "time": "10:00",
      "duration_minutes": 60,
      "agenda_items": [
        {"title": "Revenue Review", "time_allocation_minutes": 15},
        {"title": "Hiring Plan", "time_allocation_minutes": 20}
      ],
      "attendees": [
        {"email": "alice@company.com", "role": "facilitator"},
        {"email": "bob@company.com"}
      ]
    }
    ```
    """
    service = MeetingService(db)
    meeting = await service.create_meeting(data)
    return service.build_meeting_response(meeting)


@router.get("/meetings", response_model=MeetingListResponse)
async def list_meetings(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(None, description="Filter meetings on or after this date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter meetings on or before this date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search meeting titles"),
    db: AsyncSession = Depends(get_db),
):
    """List meetings with pagination and optional filters."""
    service = MeetingService(db)
    meetings, total = await service.list_meetings(
        page=page, per_page=per_page, status=status,
        date_from=date_from, date_to=date_to, search=search,
    )
    return service.build_list_response(meetings, total, page, per_page)


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full meeting details including agenda items, attendees, and computed fields."""
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return service.build_meeting_response(meeting)


@router.patch("/meetings/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: UUID,
    data: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update meeting properties. Only provided fields are changed."""
    service = MeetingService(db)
    meeting = await service.update_meeting(meeting_id, data)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return service.build_meeting_response(meeting)


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a meeting and all associated data (agenda, attendees, documents)."""
    service = MeetingService(db)
    deleted = await service.delete_meeting(meeting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meeting not found")


# ============================================
# AGENDA ITEM ENDPOINTS
# ============================================

@router.post(
    "/meetings/{meeting_id}/agenda",
    response_model=List[AgendaItemResponse],
    status_code=201,
)
async def add_agenda_items(
    meeting_id: UUID,
    items: List[AgendaItemCreate],
    db: AsyncSession = Depends(get_db),
):
    """Add one or more agenda items to a meeting.

    Items are appended to the end of the existing agenda unless
    item_order is explicitly provided.
    """
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    created = await service.add_agenda_items(meeting_id, items)
    return [AgendaItemResponse.model_validate(item) for item in created]


@router.get(
    "/meetings/{meeting_id}/agenda",
    response_model=List[AgendaItemResponse],
)
async def get_agenda(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all agenda items for a meeting, ordered by position."""
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    items = await service.get_agenda_items(meeting_id)
    return [AgendaItemResponse.model_validate(item) for item in items]


@router.patch(
    "/meetings/{meeting_id}/agenda/{item_id}",
    response_model=AgendaItemResponse,
)
async def update_agenda_item(
    meeting_id: UUID,
    item_id: UUID,
    data: AgendaItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a single agenda item. Only provided fields are changed."""
    service = MeetingService(db)
    item = await service.update_agenda_item(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Agenda item not found")
    if item.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="Agenda item not found in this meeting")
    return AgendaItemResponse.model_validate(item)


@router.delete("/meetings/{meeting_id}/agenda/{item_id}", status_code=204)
async def delete_agenda_item(
    meeting_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a single agenda item."""
    service = MeetingService(db)
    items = await service.get_agenda_items(meeting_id)
    if not any(i.id == item_id for i in items):
        raise HTTPException(status_code=404, detail="Agenda item not found in this meeting")
    deleted = await service.delete_agenda_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agenda item not found")


@router.put(
    "/meetings/{meeting_id}/agenda/reorder",
    response_model=List[AgendaItemResponse],
)
async def reorder_agenda_items(
    meeting_id: UUID,
    reorder: AgendaItemReorder,
    db: AsyncSession = Depends(get_db),
):
    """Reorder agenda items by providing an ordered list of item IDs.

    The position of each ID in the list becomes its new item_order.
    """
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    items = await service.reorder_agenda_items(meeting_id, reorder)
    return [AgendaItemResponse.model_validate(item) for item in items]


@router.post(
    "/meetings/{meeting_id}/agenda/parse",
    response_model=AgendaTextParseResponse,
)
async def parse_agenda_from_text(
    meeting_id: UUID,
    request: AgendaTextParseRequest,
    db: AsyncSession = Depends(get_db),
):
    """Parse freeform text into structured agenda items.

    Supports common formats: numbered lists, bullet points, time-stamped items,
    and items with inline presenter/time metadata.

    Returns parsed items without saving them. Use POST /meetings/{id}/agenda
    to add the parsed items to the meeting.

    Example input:
    ```
    1. Revenue Review (15 min) [Alice Johnson]
    2. Hiring Plan - Discuss Q2 headcount targets (20 min)
       - Engineering team needs
       - Sales expansion
    3. Product Roadmap Update (Presenter: Bob Smith)
    ```
    """
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    parsed_items = parse_agenda_text(request.text)

    return AgendaTextParseResponse(
        items=parsed_items,
        parse_method="rule_based",
        raw_text=request.text,
    )


# ============================================
# ATTENDEE ENDPOINTS
# ============================================

@router.post(
    "/meetings/{meeting_id}/attendees",
    response_model=List[AttendeeResponse],
    status_code=201,
)
async def add_attendees(
    meeting_id: UUID,
    attendees: List[AttendeeCreate],
    db: AsyncSession = Depends(get_db),
):
    """Add attendees to a meeting. Duplicates by email are skipped."""
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    created = await service.add_attendees(meeting_id, attendees)
    return [AttendeeResponse.model_validate(att) for att in created]


@router.get(
    "/meetings/{meeting_id}/attendees",
    response_model=List[AttendeeResponse],
)
async def get_attendees(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all attendees for a meeting."""
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    attendees = await service.get_attendees(meeting_id)
    return [AttendeeResponse.model_validate(att) for att in attendees]


@router.delete("/meetings/{meeting_id}/attendees/{attendee_id}", status_code=204)
async def remove_attendee(
    meeting_id: UUID,
    attendee_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove an attendee from a meeting."""
    service = MeetingService(db)
    attendees = await service.get_attendees(meeting_id)
    if not any(a.id == attendee_id for a in attendees):
        raise HTTPException(status_code=404, detail="Attendee not found in this meeting")
    removed = await service.remove_attendee(attendee_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Attendee not found")


# ============================================
# DOCUMENT GATHERING (stubs for next task)
# ============================================

@router.get("/meetings/{meeting_id}/documents/suggest")
async def suggest_documents(meeting_id: UUID):
    """Trigger document gathering; returns suggested documents based on agenda keywords.

    Searches connected file providers (Google Drive, OneDrive) using metadata-only
    queries derived from agenda item titles and descriptions. Never reads document content.
    """
    # TODO: Implement in "Implement document gathering and linking engine" task
    return {
        "meeting_id": str(meeting_id),
        "suggestions": [],
        "message": "Document gathering not yet implemented. Scheduled for Mar 27 - Apr 10.",
    }


@router.post("/meetings/{meeting_id}/documents/approve")
async def approve_documents(meeting_id: UUID):
    """Submit user-approved document selections from the review workflow."""
    # TODO: Implement in "Build document review and approval workflow" task
    return {
        "meeting_id": str(meeting_id),
        "approved": [],
        "message": "Document approval not yet implemented. Scheduled for Apr 3 - Apr 14.",
    }


# ============================================
# BRIEFING PACKAGE (stub for next task)
# ============================================

@router.post("/meetings/{meeting_id}/briefing")
async def generate_briefing(meeting_id: UUID):
    """Generate briefing package from approved documents and agenda."""
    # TODO: Implement in "Create pre-meeting briefing package generator" task
    return {
        "meeting_id": str(meeting_id),
        "message": "Briefing generation not yet implemented. Scheduled for Apr 3 - Apr 17.",
    }


# ============================================
# CALENDAR INTEGRATION (stub for next task)
# ============================================

@router.get("/calendar/events")
async def list_calendar_events():
    """Fetch upcoming calendar events from connected Google Calendar."""
    # TODO: Implement in calendar integration phase
    return {
        "events": [],
        "message": "Calendar integration not yet implemented. Requires Google OAuth credentials.",
    }
