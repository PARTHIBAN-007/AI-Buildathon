from __future__ import annotations

from loguru import logger

from celery import Celery

from src.config import get_settings

settings = get_settings()


celery_app = Celery("agent_tasks")
