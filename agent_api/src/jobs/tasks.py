from __future__ import annotations

from loguru import logger
from src.jobs.celery_app import celery_app
from src.infrastructure.clients.sarvam_client import SarvamClient


def trigger_sarvam_voice_call(phone: str, payload: dict | None = None):
    logger.info(f"Triggering Sarvam voice call task for {phone} with payload={payload}")
    # This function will be registered as a Celery task in a real setup
    if SarvamClient is None:
        logger.warning("Sarvam client not available; skipping call")
        return {"status": "skipped"}

    client = SarvamClient()
    # If Celery, this would be executed in worker process and awaitable
    import asyncio

    async def _call():
        try:
            return await client.trigger_call(
                phone,
                checkout_id=payload.get("checkout_id") if payload else None,
                call_summary=payload.get("call_summary") if payload else None,
                opening_line=payload.get("opening_line") if payload else None,
                user_name=payload.get("user_name") if payload else None,
                connection_id=payload.get("connection_id") if payload else None,
                agent_phone_number=payload.get("agent_phone_number") if payload else None,
                webhook_url=payload.get("webhook_url") if payload else None,
                lead_id=payload.get("lead_id") if payload else None,
            )
        finally:
            await client.close()

    try:
        return asyncio.get_event_loop().run_until_complete(_call())
    except Exception as exc:
        logger.exception(f"Sarvam call failed: {exc}")
        return {"status": "error", "error": str(exc)}
