"""Meeting Toolkit - FastAPI Backend Application"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import before_meeting, transcript, after_meeting, health
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    print(f"Starting Meeting Toolkit API ({settings.APP_ENV})")
    yield
    # Shutdown
    print("Shutting down Meeting Toolkit API")


app = FastAPI(
    title="Meeting Toolkit API",
    description="All-in-One Meeting Management - Before, Transcript Ingestion, and After Meeting processing",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route registration
app.include_router(health.router, tags=["Health"])
app.include_router(before_meeting.router, prefix="/api", tags=["Before Meeting"])
app.include_router(transcript.router, prefix="/api", tags=["Transcript Ingestion"])
app.include_router(after_meeting.router, prefix="/api", tags=["After Meeting"])
