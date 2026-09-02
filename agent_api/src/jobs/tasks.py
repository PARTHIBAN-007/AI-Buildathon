from __future__ import annotations

from loguru import logger
from src.jobs.celery_app import celery_app
from src.infrastructure.clients.sarvam_client import SarvamClient


def trigger_sarvam_voice_call(phone: str):
    logger.info(f"Triggering Sarvam voice call task for {phone}")
    # This function will be registered as a Celery task in a real setup
    # For now, call SarvamClient if available
    if SarvamClient is None:
        logger.warning("Sarvam client not available; skipping call")
        return {"status": "skipped"}

    client = SarvamClient()
    # If Celery, this would be executed in worker process and awaitable
    import asyncio

    async def _call():
        return await client.trigger_call(phone)

    try:
        return asyncio.get_event_loop().run_until_complete(_call())
    except Exception as exc:
        logger.exception(f"Sarvam call failed: {exc}")
        return {"status": "error"}
