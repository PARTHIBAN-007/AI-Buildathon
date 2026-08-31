from __future__ import annotations

from loguru import logger

try:
    from celery import Celery
except Exception:
    Celery = None

from src.config import get_settings

settings = get_settings()


if Celery is None:
    # Fallback stub
    class DummyCelery:
        def send_task(self, *args, **kwargs):
            logger.warning("Celery not installed; send_task is a no-op")
            return type("T", (), {"id": "stub-id"})()

        def control(self):
            return None

    celery_app = DummyCelery()
else:
    celery_app = Celery("agent_tasks", broker=settings.REDIS_URL)
    celery_app.conf.result_backend = settings.REDIS_URL
