"""Celery application configuration for async task processing."""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "meeting_toolkit",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minute hard limit per task
    task_soft_time_limit=240,  # 4 minute soft limit (raises exception)
    worker_prefetch_multiplier=1,  # One task at a time per worker
    task_routes={
        "app.services.tasks.process_transcript": {"queue": "transcripts"},
        "app.services.tasks.generate_document": {"queue": "documents"},
        "app.services.tasks.send_reminder": {"queue": "notifications"},
    },
)
