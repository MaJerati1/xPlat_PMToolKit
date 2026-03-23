"""Meeting Continuity Service — the bridge between Before and After.

Provides three interconnected capabilities:
  1. Transcript-to-agenda mapping: maps segments to agenda items, calculates coverage
  2. Action item tracking: dashboard with status, overdue detection, completion rates
  3. Future meeting prep: auto-generates draft agendas from outcomes

These three features form the continuity loop that makes the toolkit
more than just a transcript analyzer — it connects meeting cycles together.
"""

import uuid
import json
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.meeting import Meeting, AgendaItem
from app.models.transcript import Transcript, TranscriptSegment
from app.models.analysis import ActionItem, MeetingSummary
from app.services.llm.abstraction import LLMService, LLMRequest
from app.services.llm.mock_provider import MockProvider


# ============================================
# SCHEMAS (inline to keep it self-contained)
# ============================================

from pydantic import BaseModel, Field
import datetime as dt


class AgendaCoverageItem(BaseModel):
    """Coverage analysis for a single agenda item."""
    agenda_item_id: str
    title: str
    status: str  # discussed, deferred, not_covered
    time_allocation_minutes: Optional[int] = None
    estimated_time_spent: Optional[str] = None
    segment_count: int = 0
    key_points: List[str] = []
    segment_ids: List[str] = []


class CoverageAnalysisResponse(BaseModel):
    """Full coverage analysis for a meeting."""
    meeting_id: str
    total_agenda_items: int
    discussed: int
    deferred: int
    not_covered: int
    coverage_percentage: float
    items: List[AgendaCoverageItem] = []
    unmatched_topics: List[str] = []


class ActionTrackingDashboard(BaseModel):
    """Action item tracking dashboard data."""
    meeting_id: Optional[str] = None
    total: int = 0
    by_status: dict = {}
    by_priority: dict = {}
    confirmed: int = 0
    unconfirmed: int = 0
    overdue: int = 0
    due_this_week: int = 0
    completion_rate: float = 0.0
    owners: List[dict] = []
    items: List[dict] = []


class FuturePrepResponse(BaseModel):
    """Auto-generated draft agenda for a future meeting."""
    source_meeting_id: str
    source_meeting_title: str
    draft_agenda_items: List[dict] = []
    outstanding_action_items: List[dict] = []
    deferred_topics: List[dict] = []
    suggested_attendees: List[str] = []


class ContinuityService:
    """Service for meeting continuity — mapping, tracking, and prep."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._llm_service = self._build_llm_service()

    def _build_llm_service(self) -> LLMService:
        service = LLMService(settings)
        has_real_anthropic = (
            settings.ANTHROPIC_API_KEY
            and settings.ANTHROPIC_API_KEY.startswith("sk-ant-")
            and "your-key" not in settings.ANTHROPIC_API_KEY
            and len(settings.ANTHROPIC_API_KEY) > 20
        )
        has_real_openai = (
            settings.OPENAI_API_KEY
            and settings.OPENAI_API_KEY.startswith("sk-")
            and "your-key" not in settings.OPENAI_API_KEY
            and len(settings.OPENAI_API_KEY) > 20
        )
        if not has_real_anthropic and not has_real_openai:
            service._providers[1] = MockProvider()
        return service

    # ============================================
    # 1. TRANSCRIPT-TO-AGENDA MAPPING
    # ============================================

    async def analyze_coverage(self, meeting_id: uuid.UUID) -> CoverageAnalysisResponse:
        """Map transcript content to agenda items and analyze coverage.

        For each agenda item, determines:
          - Whether it was discussed (based on segment mapping + keyword matching)
          - Approximate time spent
          - Key points discussed
          - Which segments relate to it

        Also identifies topics discussed that weren't on the agenda.
        """
        meeting = await self._get_meeting_with_agenda(meeting_id)
        if not meeting:
            return CoverageAnalysisResponse(
                meeting_id=str(meeting_id), total_agenda_items=0,
                discussed=0, deferred=0, not_covered=0, coverage_percentage=0.0,
            )

        transcript = await self._get_transcript(meeting_id)
        if not transcript or not transcript.segments:
            # No transcript — all items are "not covered"
            items = [
                AgendaCoverageItem(
                    agenda_item_id=str(ai.id), title=ai.title,
                    status="not_covered",
                    time_allocation_minutes=ai.time_allocation_minutes,
                )
                for ai in meeting.agenda_items
            ]
            return CoverageAnalysisResponse(
                meeting_id=str(meeting_id),
                total_agenda_items=len(items),
                discussed=0, deferred=0, not_covered=len(items),
                coverage_percentage=0.0, items=items,
            )

        # Use keyword matching + LLM to map segments to agenda items
        coverage_items = await self._map_segments_to_agenda(
            meeting.agenda_items, transcript.segments
        )

        # Update agenda item statuses in DB
        for ci in coverage_items:
            if ci.status == "discussed":
                await self._update_agenda_status(uuid.UUID(ci.agenda_item_id), "discussed")
            elif ci.status == "deferred":
                await self._update_agenda_status(uuid.UUID(ci.agenda_item_id), "deferred")

        await self.db.flush()

        discussed = sum(1 for ci in coverage_items if ci.status == "discussed")
        deferred = sum(1 for ci in coverage_items if ci.status == "deferred")
        not_covered = sum(1 for ci in coverage_items if ci.status == "not_covered")
        total = len(coverage_items)

        return CoverageAnalysisResponse(
            meeting_id=str(meeting_id),
            total_agenda_items=total,
            discussed=discussed,
            deferred=deferred,
            not_covered=not_covered,
            coverage_percentage=round((discussed / total * 100) if total > 0 else 0, 1),
            items=coverage_items,
        )

    async def _map_segments_to_agenda(
        self, agenda_items: List[AgendaItem], segments: List[TranscriptSegment]
    ) -> List[AgendaCoverageItem]:
        """Map transcript segments to agenda items using keyword matching."""
        results = []

        for ai in agenda_items:
            # Build keywords from agenda item title and description
            keywords = self._extract_keywords(ai.title)
            if ai.description:
                keywords.extend(self._extract_keywords(ai.description))

            matched_segments = []
            key_points = []

            for seg in segments:
                seg_lower = seg.text.lower()
                # Check if any keyword appears in the segment
                if any(kw in seg_lower for kw in keywords):
                    matched_segments.append(str(seg.id))
                    # First matched sentence as a key point
                    point = seg.text[:150]
                    if len(seg.text) > 150:
                        point += "..."
                    key_points.append(point)

            # Determine status
            if len(matched_segments) > 0:
                status = "discussed"
            elif ai.status == "deferred":
                status = "deferred"
            else:
                status = "not_covered"

            # Estimate time spent based on segment count
            time_estimate = None
            if matched_segments:
                avg_per_segment = 30  # rough estimate: 30 seconds per segment
                total_seconds = len(matched_segments) * avg_per_segment
                if total_seconds >= 60:
                    time_estimate = f"{total_seconds // 60} minutes"
                else:
                    time_estimate = "Brief mention"

            results.append(AgendaCoverageItem(
                agenda_item_id=str(ai.id),
                title=ai.title,
                status=status,
                time_allocation_minutes=ai.time_allocation_minutes,
                estimated_time_spent=time_estimate,
                segment_count=len(matched_segments),
                key_points=key_points[:5],  # Top 5 key points
                segment_ids=matched_segments[:20],  # Limit for response size
            ))

        return results

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text for matching."""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "this", "that", "these",
            "those", "it", "its", "we", "our", "they", "their", "from", "about",
            "review", "discuss", "update", "item", "meeting", "agenda",
        }
        words = text.lower().split()
        keywords = [w.strip(".,;:!?()[]\"'") for w in words if len(w) > 2]
        return [kw for kw in keywords if kw not in stop_words]

    async def _update_agenda_status(self, item_id: uuid.UUID, status: str):
        """Update an agenda item's status."""
        result = await self.db.execute(
            select(AgendaItem).where(AgendaItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.status = status

    # ============================================
    # 2. ACTION ITEM TRACKING DASHBOARD
    # ============================================

    async def get_tracking_dashboard(
        self, meeting_id: Optional[uuid.UUID] = None
    ) -> ActionTrackingDashboard:
        """Get action item tracking dashboard with status, overdue, and owner data.

        If meeting_id is provided, scopes to that meeting.
        If None, returns a cross-meeting dashboard of all action items.
        """
        query = select(ActionItem)
        if meeting_id:
            query = query.where(ActionItem.meeting_id == meeting_id)

        result = await self.db.execute(query.order_by(ActionItem.created_at))
        items = list(result.scalars().all())

        today = date.today()
        week_end = today + timedelta(days=7)

        status_counts = {}
        priority_counts = {}
        owner_map = {}
        confirmed = 0
        unconfirmed = 0
        overdue = 0
        due_this_week = 0
        completed_count = 0

        for item in items:
            # Status counts
            status_counts[item.status] = status_counts.get(item.status, 0) + 1

            # Priority counts
            priority_counts[item.priority] = priority_counts.get(item.priority, 0) + 1

            # Confirmation
            if item.confirmed:
                confirmed += 1
            else:
                unconfirmed += 1

            # Overdue check
            if item.deadline and item.deadline < today and item.status not in ("completed", "cancelled"):
                overdue += 1

            # Due this week
            if item.deadline and today <= item.deadline <= week_end and item.status not in ("completed", "cancelled"):
                due_this_week += 1

            # Completion tracking
            if item.status == "completed":
                completed_count += 1

            # Owner aggregation
            owner = item.owner_name or "Unassigned"
            if owner not in owner_map:
                owner_map[owner] = {"name": owner, "total": 0, "completed": 0, "pending": 0, "overdue": 0}
            owner_map[owner]["total"] += 1
            if item.status == "completed":
                owner_map[owner]["completed"] += 1
            elif item.status in ("pending", "in_progress"):
                owner_map[owner]["pending"] += 1
            if item.deadline and item.deadline < today and item.status not in ("completed", "cancelled"):
                owner_map[owner]["overdue"] += 1

        completion_rate = round((completed_count / len(items) * 100) if items else 0, 1)

        # Serialize items for response
        items_data = [
            {
                "id": str(item.id),
                "meeting_id": str(item.meeting_id),
                "task": item.task,
                "owner_name": item.owner_name,
                "deadline": str(item.deadline) if item.deadline else None,
                "priority": item.priority,
                "status": item.status,
                "confirmed": item.confirmed,
                "is_overdue": bool(item.deadline and item.deadline < today and item.status not in ("completed", "cancelled")),
                "created_at": str(item.created_at),
            }
            for item in items
        ]

        return ActionTrackingDashboard(
            meeting_id=str(meeting_id) if meeting_id else None,
            total=len(items),
            by_status=status_counts,
            by_priority=priority_counts,
            confirmed=confirmed,
            unconfirmed=unconfirmed,
            overdue=overdue,
            due_this_week=due_this_week,
            completion_rate=completion_rate,
            owners=list(owner_map.values()),
            items=items_data,
        )

    # ============================================
    # 3. FUTURE MEETING PREPARATION
    # ============================================

    async def prepare_future_meeting(
        self, meeting_id: uuid.UUID
    ) -> FuturePrepResponse:
        """Generate a draft agenda for a future meeting based on outcomes.

        Analyzes:
          - Outstanding action items (pending/in_progress)
          - Deferred agenda topics (not discussed or explicitly deferred)
          - Key follow-up items from the summary
          - Attendees from the original meeting

        Produces:
          - Draft agenda items with suggested time allocations
          - List of outstanding action items for review
          - List of deferred topics to carry over
          - Suggested attendees
        """
        meeting = await self._get_meeting_with_agenda(meeting_id)
        if not meeting:
            return FuturePrepResponse(
                source_meeting_id=str(meeting_id),
                source_meeting_title="Meeting not found",
            )

        # Get outstanding action items
        result = await self.db.execute(
            select(ActionItem)
            .where(
                ActionItem.meeting_id == meeting_id,
                ActionItem.status.in_(["pending", "in_progress"]),
            )
            .order_by(ActionItem.priority.desc(), ActionItem.created_at)
        )
        outstanding_items = list(result.scalars().all())

        # Get deferred/not-covered agenda items
        deferred_items = [
            ai for ai in meeting.agenda_items
            if ai.status in ("deferred", "pending")  # pending = never updated = likely not covered
        ]

        # Get summary for follow-up context
        summary_result = await self.db.execute(
            select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
        )
        summary = summary_result.scalar_one_or_none()

        # Get attendees
        meeting_full = await self.db.execute(
            select(Meeting)
            .options(selectinload(Meeting.attendees))
            .where(Meeting.id == meeting_id)
        )
        meeting_with_attendees = meeting_full.scalar_one_or_none()
        attendee_names = []
        if meeting_with_attendees and meeting_with_attendees.attendees:
            attendee_names = [
                a.name or a.email or "Unknown"
                for a in meeting_with_attendees.attendees
            ]

        # Build draft agenda
        draft_items = []
        order = 0

        # 1. Action item review (if there are outstanding items)
        if outstanding_items:
            draft_items.append({
                "title": "Review outstanding action items",
                "description": f"Review {len(outstanding_items)} outstanding items from previous meeting",
                "time_allocation_minutes": min(5 + len(outstanding_items) * 2, 20),
                "item_order": order,
                "source": "action_items",
                "source_count": len(outstanding_items),
            })
            order += 1

        # 2. Deferred topics (carry over from previous meeting)
        for ai in deferred_items:
            draft_items.append({
                "title": ai.title,
                "description": f"Carried over from previous meeting. {ai.description or ''}".strip(),
                "time_allocation_minutes": ai.time_allocation_minutes or 10,
                "item_order": order,
                "source": "deferred_topic",
                "original_item_id": str(ai.id),
            })
            order += 1

        # 3. Follow-up items from decisions (if summary exists)
        if summary and summary.decisions_json:
            decisions = summary.decisions_json
            follow_up_decisions = [d for d in decisions if isinstance(d, dict)]
            if follow_up_decisions:
                draft_items.append({
                    "title": "Follow up on previous decisions",
                    "description": "Review implementation status of decisions made in the last meeting",
                    "time_allocation_minutes": 10,
                    "item_order": order,
                    "source": "decisions",
                    "source_count": len(follow_up_decisions),
                })
                order += 1

        # 4. Open discussion slot
        draft_items.append({
            "title": "New business and open discussion",
            "description": "Open floor for new topics and discussion items",
            "time_allocation_minutes": 10,
            "item_order": order,
            "source": "standard",
        })

        # Build outstanding items list
        outstanding_data = [
            {
                "id": str(item.id),
                "task": item.task,
                "owner_name": item.owner_name,
                "deadline": str(item.deadline) if item.deadline else None,
                "priority": item.priority,
                "status": item.status,
            }
            for item in outstanding_items
        ]

        # Build deferred topics list
        deferred_data = [
            {
                "id": str(ai.id),
                "title": ai.title,
                "description": ai.description,
                "original_time_allocation": ai.time_allocation_minutes,
            }
            for ai in deferred_items
        ]

        return FuturePrepResponse(
            source_meeting_id=str(meeting_id),
            source_meeting_title=meeting.title,
            draft_agenda_items=draft_items,
            outstanding_action_items=outstanding_data,
            deferred_topics=deferred_data,
            suggested_attendees=attendee_names,
        )

    # ============================================
    # INTERNAL HELPERS
    # ============================================

    async def _get_meeting_with_agenda(self, meeting_id: uuid.UUID) -> Optional[Meeting]:
        result = await self.db.execute(
            select(Meeting)
            .options(selectinload(Meeting.agenda_items))
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def _get_transcript(self, meeting_id: uuid.UUID) -> Optional[Transcript]:
        result = await self.db.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()
