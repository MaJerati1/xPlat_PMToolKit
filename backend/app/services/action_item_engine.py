"""Action Item Extraction Engine.

Dedicated service for extracting, linking, and managing action items.
Goes beyond the general analysis pipeline with:
  - Focused extraction prompt for higher recall
  - Segment-level traceability (links each action item to its transcript segment)
  - Batch confirm/reject operations
  - Standalone re-extraction without full re-analysis
  - Filtering and sorting capabilities
"""

import json
import uuid
from datetime import datetime, timezone, date as date_type
from typing import Optional, List

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.meeting import Meeting, AgendaItem
from app.models.transcript import Transcript, TranscriptSegment
from app.models.analysis import ActionItem, MeetingSummary
from app.schemas.analysis import ActionItemResponse
from app.services.llm.abstraction import LLMService, LLMRequest
from app.services.llm.mock_provider import MockProvider
from app.services.llm.action_prompts import (
    ACTION_ITEM_SYSTEM_ROLE,
    build_extraction_prompt,
    format_transcript_with_indices,
)


class ActionItemEngine:
    """Dedicated engine for action item extraction and management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._llm_service = self._build_llm_service()

    def _build_llm_service(self) -> LLMService:
        """Initialize LLM service with mock fallback."""
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
    # EXTRACTION
    # ============================================

    async def extract_action_items(
        self, meeting_id: uuid.UUID, replace_existing: bool = False
    ) -> dict:
        """Extract action items from a meeting transcript using the focused prompt.

        This uses the dedicated action item extraction prompt (not the general
        analysis prompt) for higher recall and segment-level traceability.

        Args:
            meeting_id: Meeting to extract from.
            replace_existing: If True, delete existing action items first.

        Returns:
            Dict with status, items list, and extraction metadata.
        """
        # Load meeting and transcript
        meeting = await self._get_meeting(meeting_id)
        if not meeting:
            return {"status": "meeting_not_found", "items": []}

        transcript = await self._get_transcript(meeting_id)
        if not transcript or not transcript.segments:
            return {"status": "no_transcript", "items": []}

        # Delete existing if replacing
        if replace_existing:
            await self.db.execute(
                delete(ActionItem).where(ActionItem.meeting_id == meeting_id)
            )
            await self.db.flush()

        # Build the focused extraction prompt
        agenda_titles = [ai.title for ai in meeting.agenda_items] if meeting.agenda_items else None
        prompt = build_extraction_prompt(agenda_titles)
        transcript_text = format_transcript_with_indices(transcript.segments)

        # Send to LLM
        try:
            llm_request = LLMRequest(
                prompt=f"{ACTION_ITEM_SYSTEM_ROLE}\n\n{prompt}",
                transcript_data=transcript_text,
                output_schema={"type": "object"},
                temperature=0.2,
                max_tokens=3000,
            )
            llm_response = await self._llm_service.process(llm_request)
        except Exception:
            try:
                mock = MockProvider()
                llm_response = await mock.process(llm_request)
            except Exception:
                return {"status": "extraction_failed", "items": []}

        # Parse LLM output
        data = llm_response.structured_data
        if not data:
            try:
                cleaned = llm_response.content.strip()
                cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                data = json.loads(cleaned)
            except (json.JSONDecodeError, AttributeError):
                return {"status": "parse_failed", "items": []}

        # Build segment lookup for linking
        segment_map = {i: seg for i, seg in enumerate(transcript.segments)}

        # Store extracted action items with segment links
        items_data = data.get("action_items", [])
        stored_items = []

        for item_data in items_data:
            task_text = item_data.get("task", "").strip()
            if not task_text:
                continue

            # Link to transcript segment if index provided
            segment_id = None
            segment_idx = item_data.get("segment_index")
            if segment_idx is not None and segment_idx in segment_map:
                segment_id = segment_map[segment_idx].id

            # If no segment link from LLM, try to match via source quote
            source_quote = item_data.get("source_quote", "")
            if not segment_id and source_quote:
                segment_id = self._find_segment_by_quote(
                    transcript.segments, source_quote
                )

            action_item = ActionItem(
                meeting_id=meeting_id,
                task=task_text,
                owner_name=item_data.get("owner"),
                priority=item_data.get("priority", "medium"),
                source_quote=source_quote,
                source_segment_id=segment_id,
                status="pending",
                confirmed=False,
            )

            # Parse deadline
            deadline_str = item_data.get("deadline")
            if deadline_str:
                try:
                    action_item.deadline = date_type.fromisoformat(deadline_str)
                except (ValueError, TypeError):
                    pass

            self.db.add(action_item)
            stored_items.append(action_item)

        await self.db.flush()
        for item in stored_items:
            await self.db.refresh(item)

        return {
            "status": "completed",
            "items": [ActionItemResponse.model_validate(ai) for ai in stored_items],
            "count": len(stored_items),
            "llm_provider": llm_response.provider,
            "llm_model": llm_response.model,
        }

    # ============================================
    # BATCH OPERATIONS
    # ============================================

    async def batch_confirm(
        self, item_ids: List[uuid.UUID]
    ) -> List[ActionItem]:
        """Confirm multiple action items at once."""
        result = await self.db.execute(
            select(ActionItem).where(ActionItem.id.in_(item_ids))
        )
        items = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        for item in items:
            item.confirmed = True
            item.confirmed_at = now
            item.updated_at = now

        await self.db.flush()
        for item in items:
            await self.db.refresh(item)
        return items

    async def batch_reject(
        self, item_ids: List[uuid.UUID]
    ) -> int:
        """Reject (delete) multiple action items at once. Returns count deleted."""
        result = await self.db.execute(
            delete(ActionItem).where(ActionItem.id.in_(item_ids))
        )
        await self.db.flush()
        return result.rowcount

    async def batch_update_status(
        self, item_ids: List[uuid.UUID], status: str
    ) -> List[ActionItem]:
        """Update status for multiple action items."""
        result = await self.db.execute(
            select(ActionItem).where(ActionItem.id.in_(item_ids))
        )
        items = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        for item in items:
            item.status = status
            item.updated_at = now
            if status == "completed" and not item.completed_at:
                item.completed_at = now

        await self.db.flush()
        for item in items:
            await self.db.refresh(item)
        return items

    # ============================================
    # FILTERING AND RETRIEVAL
    # ============================================

    async def get_action_items(
        self,
        meeting_id: uuid.UUID,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        owner: Optional[str] = None,
        confirmed_only: bool = False,
        sort_by: str = "created_at",
    ) -> List[ActionItem]:
        """Get action items with optional filtering and sorting."""
        query = select(ActionItem).where(ActionItem.meeting_id == meeting_id)

        if status:
            query = query.where(ActionItem.status == status)
        if priority:
            query = query.where(ActionItem.priority == priority)
        if owner:
            query = query.where(ActionItem.owner_name.ilike(f"%{owner}%"))
        if confirmed_only:
            query = query.where(ActionItem.confirmed == True)

        # Sorting
        sort_map = {
            "created_at": ActionItem.created_at,
            "priority": ActionItem.priority,
            "deadline": ActionItem.deadline.asc().nullslast(),
            "status": ActionItem.status,
            "owner": ActionItem.owner_name.asc().nullslast(),
        }
        if sort_by in sort_map:
            order = sort_map[sort_by]
            query = query.order_by(order)
        else:
            query = query.order_by(ActionItem.created_at)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_action_item_summary(self, meeting_id: uuid.UUID) -> dict:
        """Get a summary of action item counts by status and priority."""
        items = await self.get_action_items(meeting_id)

        status_counts = {}
        priority_counts = {}
        confirmed_count = 0
        unconfirmed_count = 0

        for item in items:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            priority_counts[item.priority] = priority_counts.get(item.priority, 0) + 1
            if item.confirmed:
                confirmed_count += 1
            else:
                unconfirmed_count += 1

        return {
            "total": len(items),
            "by_status": status_counts,
            "by_priority": priority_counts,
            "confirmed": confirmed_count,
            "unconfirmed": unconfirmed_count,
            "owners": sorted(set(
                item.owner_name for item in items if item.owner_name
            )),
        }

    # ============================================
    # INTERNAL HELPERS
    # ============================================

    async def _get_meeting(self, meeting_id: uuid.UUID) -> Optional[Meeting]:
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

    def _find_segment_by_quote(
        self, segments: List[TranscriptSegment], quote: str
    ) -> Optional[uuid.UUID]:
        """Find the segment that best matches a source quote.

        Uses simple substring matching. The LLM's source_quote should be
        a near-verbatim excerpt from the transcript.
        """
        if not quote or len(quote) < 10:
            return None

        quote_lower = quote.lower().strip()
        best_match = None
        best_overlap = 0

        for seg in segments:
            seg_lower = seg.text.lower()
            # Check substring containment
            if quote_lower in seg_lower:
                return seg.id
            # Check word overlap
            quote_words = set(quote_lower.split())
            seg_words = set(seg_lower.split())
            overlap = len(quote_words & seg_words)
            if overlap > best_overlap and overlap >= len(quote_words) * 0.6:
                best_overlap = overlap
                best_match = seg.id

        return best_match
