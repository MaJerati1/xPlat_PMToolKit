"""Quick Analyze API - standalone transcript analysis without meeting context.

Provides a single-request endpoint that accepts transcript text and returns
full analysis results (summary, decisions, action items, speakers) without
requiring the caller to create a meeting, upload a transcript, or manage
any state. Designed for the "paste and go" use case.

Behind the scenes, creates a temporary meeting record to leverage the
existing analysis pipeline, then returns everything in one response.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.meeting import Meeting
from app.schemas.transcript import TranscriptFormat
from app.services.transcript_service import TranscriptService
from app.services.analysis_service import AnalysisService

router = APIRouter()


# ============================================
# REQUEST / RESPONSE SCHEMAS
# ============================================

class QuickAnalyzeRequest(BaseModel):
    """Single-request transcript analysis."""
    text: str = Field(..., min_length=1, max_length=500000, description="Raw transcript text")
    format_hint: Optional[TranscriptFormat] = Field(
        None, description="Optional format hint (auto-detected if omitted)"
    )
    title: Optional[str] = Field(
        None, max_length=500,
        description="Optional title for the analysis (defaults to timestamp)"
    )

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Transcript text cannot be blank")
        return v


class QuickAnalyzeResponse(BaseModel):
    """Complete analysis results in a single response."""
    meeting_id: str = Field(description="Internal meeting ID (for follow-up API calls if needed)")
    status: str
    transcript_info: dict = Field(default_factory=dict)
    summary: Optional[dict] = None
    decisions: list = Field(default_factory=list)
    action_items: list = Field(default_factory=list)
    topics: list = Field(default_factory=list)
    speakers: list = Field(default_factory=list)
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


# ============================================
# ENDPOINT
# ============================================

@router.post("/quick-analyze", response_model=QuickAnalyzeResponse)
async def quick_analyze(
    request: QuickAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze a transcript in a single request — no meeting setup needed.

    Paste or send any transcript text and get back a complete analysis including
    summary, decisions, action items, topics, and speaker contributions.

    This is the simplest way to use the toolkit. No authentication, no meeting
    creation, no multi-step workflow. Just text in, insights out.

    Supports all transcript formats: plain text, SRT, VTT, CSV, JSON.
    Format is auto-detected or can be specified via format_hint.

    Example:
    ```json
    {
      "text": "Alice: Good morning everyone...\\nBob: Thanks Alice...",
      "title": "Q2 Planning Meeting"
    }
    ```

    The response includes a meeting_id that can be used for follow-up API calls
    (e.g., to update action items, re-analyze, or generate minutes).
    """
    import datetime as dt

    # 1. Create a temporary meeting
    title = request.title or f"Quick Analysis — {dt.datetime.now().strftime('%b %d, %Y %I:%M %p')}"
    meeting = Meeting(title=title, status="completed")
    db.add(meeting)
    await db.flush()

    # 2. Upload and parse transcript
    transcript_service = TranscriptService(db)
    transcript = await transcript_service.upload_and_parse(
        meeting_id=meeting.id,
        raw_text=request.text,
        format_hint=request.format_hint,
    )

    if transcript.parsed_status == "failed":
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse transcript: {transcript.parse_error or 'Unknown error'}"
        )

    transcript_info = {
        "format": transcript.original_format,
        "segments": transcript.segment_count,
        "speakers": transcript.speaker_count,
        "duration_seconds": transcript.duration_seconds,
    }

    # 3. Run LLM analysis
    analysis_service = AnalysisService(db)
    result = await analysis_service.analyze_meeting(meeting.id)

    if result.status != "completed":
        return QuickAnalyzeResponse(
            meeting_id=str(meeting.id),
            status="analysis_failed",
            transcript_info=transcript_info,
        )

    # 4. Get action items
    action_items_raw = await analysis_service.get_action_items(meeting.id)

    # 5. Build response
    summary_data = None
    decisions = []
    topics = []
    speakers = []

    if result.summary:
        summary_data = {
            "text": result.summary.summary_text,
            "generated_at": str(result.summary.generated_at) if result.summary.generated_at else None,
        }
        decisions = result.summary.decisions or []
        topics = result.summary.topics or []
        speakers = result.summary.speakers or []

    action_items = [
        {
            "id": str(ai.id),
            "task": ai.task,
            "owner": ai.owner_name,
            "deadline": str(ai.deadline) if ai.deadline else None,
            "priority": ai.priority,
            "status": ai.status,
            "confirmed": ai.confirmed,
            "source_quote": ai.source_quote,
        }
        for ai in action_items_raw
    ]

    return QuickAnalyzeResponse(
        meeting_id=str(meeting.id),
        status="completed",
        transcript_info=transcript_info,
        summary=summary_data,
        decisions=decisions,
        action_items=action_items,
        topics=topics,
        speakers=speakers,
        llm_provider=result.llm_provider,
        llm_model=result.llm_model,
    )
