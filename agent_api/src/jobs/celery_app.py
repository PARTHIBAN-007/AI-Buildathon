from __future__ import annotations

from celery import Celery
from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "agent_tasks",
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=300,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["src.jobs"])