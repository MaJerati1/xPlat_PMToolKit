"""Transcript Analysis Service - orchestrates the LLM-powered analysis pipeline.

Takes parsed transcript segments, sends them through the LLM abstraction layer,
and stores the structured output (summary, decisions, action items, topics).

Pipeline:
  1. Load transcript segments from DB
  2. Build formatted transcript text for LLM
  3. Generate analysis prompt (with optional agenda context)
  4. Send through LLM abstraction layer (Claude/GPT-4o/Ollama/Mock)
  5. Parse structured JSON output
  6. Store summary and action items in DB
  7. Return analysis results

Falls back to MockProvider when no API keys are configured,
enabling full pipeline testing without external dependencies.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.meeting import Meeting, AgendaItem
from app.models.transcript import Transcript, TranscriptSegment
from app.models.analysis import MeetingSummary, ActionItem
from app.schemas.analysis import (
    AnalysisResponse, SummaryResponse, ActionItemResponse,
    ActionItemUpdate, LLMAnalysisOutput,
)
from app.services.llm.abstraction import LLMService, LLMRequest, IsolationTier
from app.services.llm.mock_provider import MockProvider
from app.services.llm.prompts import build_analysis_prompt, SYSTEM_ROLE


class AnalysisService:
    """Service layer for transcript analysis and action item management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._llm_service = self._build_llm_service()

    def _build_llm_service(self) -> LLMService:
        """Initialize LLM service, falling back to mock if no real API keys configured."""
        service = LLMService(settings)
        # Check for actual API keys (not placeholders like "sk-ant-your-key-here")
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
    # ANALYSIS PIPELINE
    # ============================================

    async def analyze_meeting(
        self, meeting_id: uuid.UUID, reanalyze: bool = False
    ) -> AnalysisResponse:
        """Run the full analysis pipeline for a meeting.

        Args:
            meeting_id: Meeting to analyze.
            reanalyze: If True, delete existing analysis and re-run.

        Returns:
            AnalysisResponse with summary and action items.
        """
        # 1. Load meeting with agenda
        meeting = await self._get_meeting(meeting_id)
        if not meeting:
            return AnalysisResponse(
                meeting_id=meeting_id, status="meeting_not_found"
            )

        # 2. Load transcript with segments
        transcript = await self._get_transcript(meeting_id)
        if not transcript or not transcript.segments:
            return AnalysisResponse(
                meeting_id=meeting_id, status="no_transcript"
            )

        # 3. Check for existing analysis
        existing_summary = await self._get_summary(meeting_id)
        if existing_summary and not reanalyze:
            action_items = await self.get_action_items(meeting_id)
            return self._build_response(
                meeting_id, "completed", existing_summary, action_items
            )

        # 4. Delete existing analysis if re-analyzing
        if reanalyze and existing_summary:
            await self.db.delete(existing_summary)
            await self.db.execute(
                delete(ActionItem).where(ActionItem.meeting_id == meeting_id)
            )
            await self.db.flush()

        # 5. Build transcript text for LLM
        transcript_text = self._format_transcript(transcript.segments)

        # 6. Build prompt with optional agenda context
        agenda_titles = [ai.title for ai in meeting.agenda_items] if meeting.agenda_items else None
        prompt = build_analysis_prompt(agenda_titles)

        # 7. Send to LLM (with automatic fallback to MockProvider)
        try:
            llm_request = LLMRequest(
                prompt=f"{SYSTEM_ROLE}\n\n{prompt}",
                transcript_data=transcript_text,
                output_schema={"type": "object"},  # Signal structured output expected
                temperature=0.2,
                max_tokens=4000,
            )
            llm_response = await self._llm_service.process(llm_request)
        except Exception:
            # Primary LLM failed — fall back to MockProvider
            try:
                mock = MockProvider()
                llm_response = await mock.process(llm_request)
            except Exception as e2:
                return AnalysisResponse(
                    meeting_id=meeting_id,
                    status="failed",
                )

        # 8. Parse LLM output
        analysis_data = llm_response.structured_data
        if not analysis_data:
            try:
                cleaned = llm_response.content.strip()
                cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                analysis_data = json.loads(cleaned)
            except (json.JSONDecodeError, AttributeError):
                return AnalysisResponse(
                    meeting_id=meeting_id,
                    status="failed",
                )

        # 9. Store summary
        summary = MeetingSummary(
            meeting_id=meeting_id,
            summary_text=analysis_data.get("summary", ""),
            decisions_json=analysis_data.get("decisions", []),
            topics_json=analysis_data.get("topics", []),
            speakers_json=analysis_data.get("speakers", []),
            llm_provider=llm_response.provider,
            llm_model=llm_response.model,
            llm_tier=llm_response.tier,
        )
        self.db.add(summary)
        await self.db.flush()

        # 10. Store action items
        action_items_data = analysis_data.get("action_items", [])
        stored_items = []
        for item_data in action_items_data:
            action_item = ActionItem(
                meeting_id=meeting_id,
                task=item_data.get("task", ""),
                owner_name=item_data.get("owner"),
                priority=item_data.get("priority", "medium"),
                source_quote=item_data.get("source_quote"),
                status="pending",
                confirmed=False,
            )
            # Parse deadline if provided
            deadline_str = item_data.get("deadline")
            if deadline_str:
                try:
                    from datetime import date as date_type
                    action_item.deadline = date_type.fromisoformat(deadline_str)
                except (ValueError, TypeError):
                    pass

            self.db.add(action_item)
            stored_items.append(action_item)

        await self.db.flush()
        await self.db.refresh(summary)
        for item in stored_items:
            await self.db.refresh(item)

        return self._build_response(meeting_id, "completed", summary, stored_items)

    # ============================================
    # SUMMARY RETRIEVAL
    # ============================================

    async def get_summary(self, meeting_id: uuid.UUID) -> Optional[MeetingSummary]:
        """Get the meeting summary if it exists."""
        return await self._get_summary(meeting_id)

    # ============================================
    # ACTION ITEM MANAGEMENT
    # ============================================

    async def get_action_items(self, meeting_id: uuid.UUID) -> List[ActionItem]:
        """Get all action items for a meeting."""
        result = await self.db.execute(
            select(ActionItem)
            .where(ActionItem.meeting_id == meeting_id)
            .order_by(ActionItem.created_at)
        )
        return list(result.scalars().all())

    async def update_action_item(
        self, item_id: uuid.UUID, data: ActionItemUpdate
    ) -> Optional[ActionItem]:
        """Update an action item (confirm, reassign, change status, etc.)."""
        result = await self.db.execute(
            select(ActionItem).where(ActionItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                if hasattr(value, "value"):  # Enum
                    setattr(item, field, value.value)
                else:
                    setattr(item, field, value)

        # Track confirmation timestamp
        if data.confirmed is True and not item.confirmed_at:
            item.confirmed_at = datetime.now(timezone.utc)

        # Track completion timestamp
        if data.status and data.status.value == "completed" and not item.completed_at:
            item.completed_at = datetime.now(timezone.utc)

        item.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    # ============================================
    # INTERNAL HELPERS
    # ============================================

    async def _get_meeting(self, meeting_id: uuid.UUID) -> Optional[Meeting]:
        """Load meeting with agenda items."""
        result = await self.db.execute(
            select(Meeting)
            .options(selectinload(Meeting.agenda_items))
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def _get_transcript(self, meeting_id: uuid.UUID) -> Optional[Transcript]:
        """Load transcript with segments."""
        result = await self.db.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def _get_summary(self, meeting_id: uuid.UUID) -> Optional[MeetingSummary]:
        """Load existing meeting summary."""
        result = await self.db.execute(
            select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()

    def _format_transcript(self, segments: List[TranscriptSegment]) -> str:
        """Format transcript segments into readable text for the LLM."""
        lines = []
        for seg in segments:
            prefix = ""
            if seg.speaker_name:
                prefix = f"{seg.speaker_name}: "
            elif seg.speaker_id:
                prefix = f"{seg.speaker_id}: "

            timestamp = ""
            if seg.start_time is not None:
                mins = int(seg.start_time // 60)
                secs = int(seg.start_time % 60)
                timestamp = f"[{mins:02d}:{secs:02d}] "

            lines.append(f"{timestamp}{prefix}{seg.text}")

        return "\n".join(lines)

    def _build_response(
        self,
        meeting_id: uuid.UUID,
        status: str,
        summary: Optional[MeetingSummary],
        action_items: List[ActionItem],
    ) -> AnalysisResponse:
        """Build the API response from DB objects."""
        summary_resp = None
        if summary:
            summary_resp = SummaryResponse(
                id=summary.id,
                meeting_id=summary.meeting_id,
                summary_text=summary.summary_text,
                decisions=summary.decisions_json or [],
                topics=summary.topics_json or [],
                speakers=summary.speakers_json or [],
                llm_provider=summary.llm_provider,
                llm_model=summary.llm_model,
                llm_tier=summary.llm_tier,
                generated_at=summary.generated_at,
            )

        return AnalysisResponse(
            meeting_id=meeting_id,
            status=status,
            summary=summary_resp,
            action_items=[ActionItemResponse.model_validate(ai) for ai in action_items],
            llm_provider=summary.llm_provider if summary else None,
            llm_model=summary.llm_model if summary else None,
            llm_tier=summary.llm_tier if summary else None,
        )
