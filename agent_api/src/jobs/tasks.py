from __future__ import annotations

import asyncio
from loguru import logger

from src.infrastructure.clients.sarvam_client import SarvamClient
from src.jobs.celery_app import celery_app


@celery_app.task(name="tasks.trigger_sarvam_voice_call")
def trigger_sarvam_voice_call(phone: str, payload: dict | None = None) -> dict:
    """Trigger an outbound Sarvam voice call for a failed-payment recovery workflow."""
    logger.info(f"Triggering Sarvam voice call task for phone={phone} with payload={payload}")

    if not phone:
        logger.warning("No phone number provided for Sarvam voice task; skipping.")
        return {"status": "skipped", "reason": "missing_phone"}

    p = payload or {}

    async def _execute_call() -> dict:
        client = SarvamClient()
        try:
            return await client.trigger_call(
                phone=phone,
                checkout_id=p.get("checkout_id"),
                call_summary=p.get("call_summary"),
                opening_line=p.get("opening_line"),
                user_name=p.get("user_name"),
                connection_id=p.get("connection_id"),
                agent_phone_number=p.get("agent_phone_number"),
                webhook_url=p.get("webhook_url"),
                lead_id=p.get("lead_id"),
            )
        finally:
            await client.close()

    try:
        return asyncio.run(_execute_call())
    except Exception as exc:
        logger.exception(f"Sarvam call execution failed for phone={phone}: {exc}")
        return {"status": "error", "error": str(exc)}