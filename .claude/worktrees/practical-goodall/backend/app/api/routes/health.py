"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Application health check."""
    return {"status": "healthy", "service": "meeting-toolkit-api", "version": "0.1.0"}
