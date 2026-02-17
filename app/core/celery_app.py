"""Celery application for background tasks (video processing, notifications)."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "pixer",
    broker=settings.CELERY_BROKER_URL,
    include=["app.workers.video_processing", "app.workers.notifications"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
