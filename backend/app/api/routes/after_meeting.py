"""After Meeting module API routes.

Fully implemented endpoints for:
  - LLM-powered transcript analysis (summary, decisions, action items, topics)
  - Dedicated action item extraction engine with segment traceability
  - Meeting summary retrieval
  - Action item CRUD (list, update, confirm) with filtering
  - Batch operations (confirm, reject, status update)
  - Action item summary/counts
  - Meeting minutes generation (stub for document generation task)
  - Future meeting prep (stub for future task)
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.analysis import (
    AnalysisRequest, AnalysisResponse,
    SummaryResponse, ActionItemResponse, ActionItemUpdate,
    ExtractionRequest, ExtractionResponse,
    BatchConfirmRequest, BatchConfirmResponse,
    BatchRejectRequest, BatchRejectResponse,
    BatchStatusRequest,
    ActionItemSummaryResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.action_item_engine import ActionItemEngine

router = APIRouter()


# ============================================
# LLM ANALYSIS
# ============================================

@router.post("/meetings/{meeting_id}/analyze")
async def analyze_transcript(
    meeting_id: UUID,
    request: AnalysisRequest = AnalysisRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger full LLM analysis of the uploaded transcript."""
    import logging
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    logger = logging.getLogger(__name__)

    try:
        service = AnalysisService(db)
        result = await service.analyze_meeting(meeting_id, reanalyze=request.reanalyze)
    except Exception as e:
        logger.error(f"Analysis exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    if result.status == "meeting_not_found":
        raise HTTPException(status_code=404, detail="Meeting not found")
    if result.status == "no_transcript":
        raise HTTPException(status_code=409, detail="No transcript found. Upload a transcript first.")

    # Serialize with multiple fallback strategies
    try:
        data = jsonable_encoder(result)
        return JSONResponse(content=data)
    except Exception as e1:
        logger.error(f"jsonable_encoder failed: {e1}", exc_info=True)
        try:
            data = result.model_dump(mode="json")
            return JSONResponse(content=data)
        except Exception as e2:
            logger.error(f"model_dump also failed: {e2}", exc_info=True)
            # Manual fallback — guaranteed to work
            summary_data = None
            if result.summary:
                try:
                    summary_data = {
                        "id": str(result.summary.id),
                        "meeting_id": str(result.summary.meeting_id),
                        "summary_text": result.summary.summary_text,
                        "decisions": result.summary.decisions,
                        "topics": result.summary.topics,
                        "speakers": result.summary.speakers,
                        "llm_provider": result.summary.llm_provider,
                        "llm_model": result.summary.llm_model,
                        "llm_tier": result.summary.llm_tier,
                        "generated_at": str(result.summary.generated_at) if result.summary.generated_at else None,
                    }
                except Exception:
                    summary_data = {"summary_text": "Analysis completed but summary serialization failed."}

            action_data = []
            for ai in result.action_items:
                try:
                    action_data.append(jsonable_encoder(ai))
                except Exception:
                    try:
                        action_data.append({
                            "id": str(ai.id),
                            "meeting_id": str(ai.meeting_id),
                            "task": ai.task,
                            "owner_name": ai.owner_name,
                            "priority": ai.priority,
                            "status": ai.status,
                            "confirmed": ai.confirmed,
                            "source_quote": ai.source_quote,
                            "created_at": str(ai.created_at) if ai.created_at else None,
                            "updated_at": str(ai.updated_at) if ai.updated_at else None,
                        })
                    except Exception:
                        pass

            return JSONResponse(content={
                "meeting_id": str(meeting_id),
                "status": "completed",
                "summary": summary_data,
                "action_items": action_data,
                "llm_provider": result.llm_provider,
                "llm_model": result.llm_model,
                "llm_tier": result.llm_tier,
            })


# ============================================
# ACTION ITEM EXTRACTION ENGINE
# ============================================

@router.post(
    "/meetings/{meeting_id}/extract-actions",
    response_model=ExtractionResponse,
)
async def extract_action_items(
    meeting_id: UUID,
    request: ExtractionRequest = ExtractionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Extract action items using the dedicated extraction engine.

    Uses a focused prompt optimized for action item detection with
    segment-level traceability. More thorough than the general analysis.

    Set `replace_existing: true` to clear previous action items first.
    """
    engine = ActionItemEngine(db)
    result = await engine.extract_action_items(
        meeting_id, replace_existing=request.replace_existing
    )

    if result["status"] == "meeting_not_found":
        raise HTTPException(status_code=404, detail="Meeting not found")
    if result["status"] == "no_transcript":
        raise HTTPException(
            status_code=409,
            detail="No transcript found. Upload a transcript first."
        )

    return ExtractionResponse(**result)


# ============================================
# SUMMARY RETRIEVAL
# ============================================

@router.get("/meetings/{meeting_id}/summary", response_model=SummaryResponse)
async def get_meeting_summary(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the generated meeting summary."""
    service = AnalysisService(db)
    summary = await service.get_summary(meeting_id)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail="No summary found. Run POST /meetings/{id}/analyze first."
        )

    return SummaryResponse(
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


# ============================================
# ACTION ITEMS — LIST WITH FILTERING
# ============================================

@router.get(
    "/meetings/{meeting_id}/action-items",
    response_model=List[ActionItemResponse],
)
async def list_action_items(
    meeting_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status: pending, in_progress, completed, cancelled"),
    priority: Optional[str] = Query(None, description="Filter by priority: high, medium, low"),
    owner: Optional[str] = Query(None, description="Filter by owner name (partial match)"),
    confirmed_only: bool = Query(False, description="Show only confirmed items"),
    sort_by: str = Query("created_at", description="Sort by: created_at, priority, deadline, status, owner"),
    db: AsyncSession = Depends(get_db),
):
    """List action items with optional filtering and sorting.

    Supports filtering by status, priority, owner, and confirmation state.
    """
    engine = ActionItemEngine(db)
    items = await engine.get_action_items(
        meeting_id,
        status=status,
        priority=priority,
        owner=owner,
        confirmed_only=confirmed_only,
        sort_by=sort_by,
    )
    return [ActionItemResponse.model_validate(item) for item in items]


@router.get(
    "/meetings/{meeting_id}/action-items/summary",
    response_model=ActionItemSummaryResponse,
)
async def get_action_item_summary(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get action item counts by status, priority, and confirmation state."""
    engine = ActionItemEngine(db)
    return await engine.get_action_item_summary(meeting_id)


# ============================================
# ACTION ITEMS — SINGLE ITEM UPDATE
# ============================================

@router.patch("/action-items/{action_item_id}", response_model=ActionItemResponse)
async def update_action_item(
    action_item_id: UUID,
    data: ActionItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an action item: confirm, reassign, change status/priority, edit task."""
    service = AnalysisService(db)
    item = await service.update_action_item(action_item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
    return ActionItemResponse.model_validate(item)


# ============================================
# ACTION ITEMS — BATCH OPERATIONS
# ============================================

@router.post(
    "/meetings/{meeting_id}/action-items/batch-confirm",
    response_model=BatchConfirmResponse,
)
async def batch_confirm_action_items(
    meeting_id: UUID,
    request: BatchConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm multiple action items at once.

    Marks all specified items as confirmed with a timestamp.
    """
    engine = ActionItemEngine(db)
    items = await engine.batch_confirm(request.item_ids)
    return BatchConfirmResponse(
        confirmed_count=len(items),
        items=[ActionItemResponse.model_validate(item) for item in items],
    )


@router.post(
    "/meetings/{meeting_id}/action-items/batch-reject",
    response_model=BatchRejectResponse,
)
async def batch_reject_action_items(
    meeting_id: UUID,
    request: BatchRejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reject (delete) multiple action items at once.

    Permanently removes the specified items. Use for AI-extracted items
    that are incorrect or not actually action items.
    """
    engine = ActionItemEngine(db)
    count = await engine.batch_reject(request.item_ids)
    return BatchRejectResponse(rejected_count=count)


@router.post(
    "/meetings/{meeting_id}/action-items/batch-status",
    response_model=List[ActionItemResponse],
)
async def batch_update_status(
    meeting_id: UUID,
    request: BatchStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update status for multiple action items at once."""
    engine = ActionItemEngine(db)
    items = await engine.batch_update_status(request.item_ids, request.status.value)
    return [ActionItemResponse.model_validate(item) for item in items]


# ============================================
# ACTION ITEM TRACKING DASHBOARD
# ============================================

@router.get("/meetings/{meeting_id}/action-items/tracking")
async def get_action_tracking_dashboard(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get action item tracking dashboard for a meeting.

    Returns status counts, overdue items, completion rate,
    owner breakdown, and due-this-week items.
    """
    from app.services.continuity_service import ContinuityService
    service = ContinuityService(db)
    return await service.get_tracking_dashboard(meeting_id)


@router.get("/action-items/tracking")
async def get_global_tracking_dashboard(
    db: AsyncSession = Depends(get_db),
):
    """Get global action item tracking dashboard across all meetings.

    Returns an aggregate view of all action items with status,
    overdue, and owner data across the entire workspace.
    """
    from app.services.continuity_service import ContinuityService
    service = ContinuityService(db)
    return await service.get_tracking_dashboard()


# ============================================
# MEETING MINUTES (stub for document generation task)
# ============================================

@router.post("/meetings/{meeting_id}/minutes")
async def generate_minutes(meeting_id: UUID):
    """Generate formatted meeting minutes document (Word/PDF)."""
    return {
        "meeting_id": str(meeting_id),
        "message": "Minutes generation not yet implemented. Scheduled for May 8-15.",
    }


# ============================================
# FUTURE MEETING PREPARATION
# ============================================

@router.post("/meetings/{meeting_id}/next-agenda")
async def generate_next_agenda(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate a draft agenda for the next meeting based on outcomes.

    Analyzes outstanding action items, deferred topics, and decisions
    from the current meeting to produce a structured draft agenda.

    Returns:
      - Draft agenda items with suggested time allocations
      - Outstanding action items for review
      - Deferred topics to carry over
      - Suggested attendees from the original meeting
    """
    from app.services.continuity_service import ContinuityService
    service = ContinuityService(db)
    result = await service.prepare_future_meeting(meeting_id)
    return result


# ============================================
# DOCUMENT DOWNLOADS (stub for future task)
# ============================================

@router.get("/meetings/{meeting_id}/documents/{doc_id}/download")
async def download_document(meeting_id: UUID, doc_id: UUID):
    """Download a generated document (minutes, briefing, or draft agenda)."""
    return {
        "meeting_id": str(meeting_id),
        "doc_id": str(doc_id),
        "message": "Document download not yet implemented.",
    }
