"""Before Meeting module API routes.

Fully implemented endpoints for:
  - Meeting CRUD (create, read, update, delete, list)
  - Agenda item CRUD (add, update, delete, reorder, parse from text)
  - Attendee management (add, list, remove)
  - Document gathering and approval workflow
  - Briefing package generation (JSON + Word document)
  - Calendar event import (stub for future implementation)
"""

import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.schemas.meeting import (
    MeetingCreate, MeetingUpdate, MeetingResponse, MeetingListResponse,
    AgendaItemCreate, AgendaItemUpdate, AgendaItemResponse, AgendaItemReorder,
    AttendeeCreate, AttendeeResponse,
    AgendaTextParseRequest, AgendaTextParseResponse,
    DocumentSuggestResponse, DocumentSuggestion,
    DocumentApproveRequest, DocumentApproveResponse,
    BriefingRequest, BriefingResponse, BriefingSectionResponse,
)
from app.services.meeting_service import MeetingService
from app.parsers.agenda_parser import parse_agenda_text

logger = logging.getLogger(__name__)

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

@router.get("/meetings/{meeting_id}/documents/suggest", response_model=DocumentSuggestResponse)
async def suggest_documents(
    meeting_id: UUID,
    access_token: Optional[str] = Header(None, alias="X-Google-Access-Token"),
    max_per_item: int = Query(5, ge=1, le=20),
    recency_days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Search connected storage for documents matching this meeting's agenda items.

    Uses metadata-only matching (file names, folders, modification dates) — never
    reads document content.

    The Google access token can be provided either:
    1. In the `X-Google-Access-Token` header, or
    2. Automatically from the stored OAuth token (after connecting via /api/auth/google)
    """
    from app.services.document_gathering import DocumentGatheringService
    from app.api.routes.google_auth import _token_store

    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Get agenda item titles
    agenda = await service.get_agenda_items(meeting_id)
    if not agenda:
        return DocumentSuggestResponse(
            meeting_id=meeting_id,
            suggestions=[],
            message="No agenda items found. Add agenda items first, then search for documents.",
        )

    agenda_titles = [item.title for item in agenda]

    # Auto-fetch token from OAuth store if not provided in header
    if not access_token:
        access_token = _token_store.get("access_token")

    if not access_token:
        return DocumentSuggestResponse(
            meeting_id=meeting_id,
            suggestions=[],
            message="No Google access token provided. Connect your Google account to search Drive for documents. Send the token in the X-Google-Access-Token header.",
        )

    try:
        gathering = DocumentGatheringService(db)
        results = await gathering.gather_documents(
            meeting_id=meeting_id,
            agenda_titles=agenda_titles,
            access_token=access_token,
            max_per_item=max_per_item,
            recency_days=recency_days,
        )

        suggestions = [DocumentSuggestion(**r) for r in results]
        return DocumentSuggestResponse(
            meeting_id=meeting_id,
            suggestions=suggestions,
            message=f"Found {len(suggestions)} document(s) matching your agenda items.",
        )
    except Exception as e:
        logger.error(f"Document gathering failed: {e}")
        return DocumentSuggestResponse(
            meeting_id=meeting_id,
            suggestions=[],
            message=f"Document search failed: {str(e)}. Check your Google account connection.",
        )


@router.post("/meetings/{meeting_id}/documents/approve", response_model=DocumentApproveResponse)
async def approve_documents(
    meeting_id: UUID,
    request: DocumentApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve selected documents from the suggestion list.

    Takes a list of file IDs that the user approved from the suggestion workflow.
    Creates Document records in the database linked to this meeting.
    Only approved documents will be included in the briefing package.
    """
    from app.models.meeting import Document
    from sqlalchemy import select

    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not request.approved_file_ids:
        return DocumentApproveResponse(
            meeting_id=meeting_id,
            approved_count=0,
            documents=[],
        )

    approved_docs = []
    for file_id in request.approved_file_ids:
        # Check if already approved (avoid duplicates)
        existing = await db.execute(
            select(Document).where(
                Document.meeting_id == meeting_id,
                Document.source_file_id == file_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        doc = Document(
            meeting_id=meeting_id,
            source="google_drive",
            source_file_id=file_id,
            file_name=file_id,  # Will be enriched if we have the name
            approved=True,
            approved_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(doc)
        approved_docs.append(doc)

    await db.flush()
    for doc in approved_docs:
        await db.refresh(doc)
    await db.commit()

    return DocumentApproveResponse(
        meeting_id=meeting_id,
        approved_count=len(approved_docs),
        documents=[{
            "id": str(d.id),
            "file_name": d.file_name,
            "source_file_id": d.source_file_id,
            "approved": d.approved,
        } for d in approved_docs],
    )


@router.post("/meetings/{meeting_id}/documents/approve-with-metadata")
async def approve_documents_with_metadata(
    meeting_id: UUID,
    documents: List[dict],
    db: AsyncSession = Depends(get_db),
):
    """Approve documents with full metadata from the suggestion results.

    Accepts the full suggestion objects so we can store file names, URLs, and types.
    """
    from app.models.meeting import Document
    from datetime import datetime, timezone
    from sqlalchemy import select

    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    approved_docs = []
    for doc_data in documents:
        file_id = doc_data.get("file_id")
        if not file_id:
            continue

        # Skip duplicates
        existing = await db.execute(
            select(Document).where(
                Document.meeting_id == meeting_id,
                Document.source_file_id == file_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        doc = Document(
            meeting_id=meeting_id,
            source="google_drive",
            source_file_id=file_id,
            file_name=doc_data.get("name", file_id),
            file_url=doc_data.get("web_view_link"),
            mime_type=doc_data.get("mime_type"),
            approved=True,
            approved_at=datetime.now(timezone.utc),
            metadata_json={
                "owners": doc_data.get("owners", []),
                "modified_time": doc_data.get("modified_time"),
                "matched_keyword": doc_data.get("matched_keyword"),
            },
        )
        db.add(doc)
        approved_docs.append(doc)

    await db.flush()
    for doc in approved_docs:
        await db.refresh(doc)
    await db.commit()

    return {
        "meeting_id": str(meeting_id),
        "approved_count": len(approved_docs),
        "documents": [{
            "id": str(d.id),
            "file_name": d.file_name,
            "source_file_id": d.source_file_id,
            "file_url": d.file_url,
            "mime_type": d.mime_type,
            "approved": d.approved,
        } for d in approved_docs],
    }


@router.get("/meetings/{meeting_id}/documents")
async def list_meeting_documents(
    meeting_id: UUID,
    approved_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """List all documents linked to a meeting."""
    from app.models.meeting import Document
    from sqlalchemy import select

    query = select(Document).where(Document.meeting_id == meeting_id)
    if approved_only:
        query = query.where(Document.approved == True)
    query = query.order_by(Document.created_at.desc())

    result = await db.execute(query)
    docs = list(result.scalars().all())

    return {
        "meeting_id": str(meeting_id),
        "total": len(docs),
        "documents": [{
            "id": str(d.id),
            "file_name": d.file_name,
            "source": d.source,
            "source_file_id": d.source_file_id,
            "file_url": d.file_url,
            "mime_type": d.mime_type,
            "approved": d.approved,
            "approved_at": d.approved_at.isoformat() if d.approved_at else None,
            "metadata": d.metadata_json,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        } for d in docs],
    }


@router.delete("/meetings/{meeting_id}/documents/{document_id}", status_code=204)
async def remove_document(
    meeting_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a document from a meeting."""
    from app.models.meeting import Document
    from sqlalchemy import select

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.meeting_id == meeting_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.delete(doc)
    await db.commit()


# ============================================
# BRIEFING PACKAGE
# ============================================

@router.post("/meetings/{meeting_id}/briefing")
async def generate_briefing(
    meeting_id: UUID,
    request: BriefingRequest = BriefingRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Generate a pre-meeting briefing package.

    Compiles the meeting agenda, attendee list, approved documents, and outstanding
    action items from previous meetings into a consolidated briefing.

    Supports two output formats:
    - **json** (default): Returns structured JSON for frontend rendering.
    - **docx**: Returns a downloadable Word document.
    """
    from app.services.briefing_generator import BriefingGeneratorService

    try:
        generator = BriefingGeneratorService(db)

        if request.format == "docx":
            docx_bytes = await generator.generate_briefing_docx(meeting_id)
            return Response(
                content=docx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.presentation",
                headers={
                    "Content-Disposition": f"attachment; filename=briefing_{meeting_id}.docx"
                },
            )

        briefing = await generator.generate_briefing(
            meeting_id,
            include_outstanding_actions=request.include_outstanding_actions,
            include_documents=request.include_documents,
        )

        return briefing.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Briefing generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Briefing generation failed: {str(e)}")


# ============================================
# CALENDAR INTEGRATION
# ============================================

@router.get("/calendar/events")
async def list_calendar_events(
    days_ahead: int = Query(14, ge=1, le=90),
    max_results: int = Query(20, ge=1, le=50),
):
    """Fetch upcoming calendar events from connected Google Calendar.

    Returns events for the next N days. Requires Google OAuth connection
    (connect at /api/auth/google first).
    """
    from app.services.calendar_service import GoogleCalendarService
    from app.api.routes.google_auth import _token_store

    token = _token_store.get("access_token")
    if not token:
        return {
            "events": [],
            "connected": False,
            "message": "Google account not connected. Visit /api/auth/google to connect.",
        }

    try:
        cal = GoogleCalendarService(token)
        events = cal.list_upcoming_events(max_results=max_results, days_ahead=days_ahead)
        return {
            "events": [e.to_dict() for e in events],
            "connected": True,
            "total": len(events),
            "days_ahead": days_ahead,
        }
    except Exception as e:
        logger.error(f"Calendar fetch failed: {e}")
        return {
            "events": [],
            "connected": True,
            "error": str(e),
            "message": "Failed to fetch calendar events. Token may have expired — reconnect at /api/auth/google.",
        }


@router.post("/calendar/events/{event_id}/import")
async def import_calendar_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Import a Google Calendar event as a Meeting Toolkit meeting.

    Creates a meeting with:
    - Title, date, time, duration from the calendar event
    - Meeting link (Google Meet, Zoom, etc.) if present
    - Attendees from the event's guest list
    - Agenda items parsed from the event description (bullet points, numbered lists)

    The imported meeting can then be used for document gathering, briefing generation,
    and transcript analysis.
    """
    from app.services.calendar_service import GoogleCalendarService
    from app.api.routes.google_auth import _token_store
    from app.models.meeting import Meeting, AgendaItem, MeetingAttendee
    from sqlalchemy import select

    token = _token_store.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Google account not connected. Visit /api/auth/google first.")

    # Check if already imported
    existing = await db.execute(
        select(Meeting).where(Meeting.calendar_event_id == event_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This calendar event has already been imported.")

    try:
        cal = GoogleCalendarService(token)
        event = cal.get_event(event_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch event from Google Calendar: {str(e)}")

    # Create the meeting
    from datetime import date as date_type, time as time_type
    meeting = Meeting(
        title=event.title,
        calendar_event_id=event.google_event_id,
        calendar_provider="google",
        meeting_link=event.meeting_link,
        notes=event.description[:2000] if event.description else None,
        status="scheduled",
    )

    # Parse and set date/time
    if event.date:
        try:
            meeting.date = date_type.fromisoformat(event.date)
        except (ValueError, TypeError):
            pass
    if event.time:
        try:
            meeting.time = time_type.fromisoformat(event.time)
        except (ValueError, TypeError):
            pass
    if event.duration_minutes:
        meeting.duration_minutes = event.duration_minutes

    db.add(meeting)
    await db.flush()
    await db.refresh(meeting)

    # Add attendees
    attendees_added = []
    for att_data in event.attendees:
        attendee = MeetingAttendee(
            meeting_id=meeting.id,
            email=att_data["email"],
            name=att_data["name"],
            role="organizer" if att_data.get("is_organizer") else "participant",
            rsvp_status=att_data.get("rsvp_status", "pending"),
        )
        db.add(attendee)
        attendees_added.append(attendee)

    # Parse agenda items from description
    agenda_items_added = []
    parsed_items = event.extract_agenda_items()
    for i, item_data in enumerate(parsed_items):
        agenda_item = AgendaItem(
            meeting_id=meeting.id,
            title=item_data["title"],
            item_order=i,
            status="pending",
        )
        db.add(agenda_item)
        agenda_items_added.append(agenda_item)

    await db.commit()
    await db.refresh(meeting)

    return {
        "message": f"Successfully imported '{event.title}' from Google Calendar",
        "meeting_id": str(meeting.id),
        "title": event.title,
        "date": event.date,
        "time": event.time,
        "duration_minutes": event.duration_minutes,
        "meeting_link": event.meeting_link,
        "attendees_imported": len(attendees_added),
        "agenda_items_parsed": len(agenda_items_added),
        "agenda_items": [{"title": a.title} for a in agenda_items_added],
        "google_event_link": event.html_link,
    }
