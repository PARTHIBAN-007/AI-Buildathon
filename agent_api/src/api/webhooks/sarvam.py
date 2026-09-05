from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Request, Response
from loguru import logger

from src.agent.graph import append_voice_summary
from src.infrastructure.postgres.repository import list_active_checkouts

router = APIRouter()



@router.post("/sarvam")
async def sarvam_voice_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Inbound Sarvam Voice Webhook Endpoint.

    Processes call summaries asynchronously in the background to return HTTP 200 OK
    immediately, preventing Sarvam delivery retries and timeouts.
    """
    try:
        payload = await request.json()
    except Exception as parse_err:
        logger.error(f"Failed to parse Sarvam webhook JSON payload: {parse_err}")
        return Response(status_code=200)

    logger.info(f"Received Sarvam voice webhook payload: {payload}")

    try:
        status = str(payload.get("status", "")).lower()

        
        metadata: Dict[str, Any] = (
            payload.get("metadata")
            or payload.get("webhook_config", {}).get("metadata", {})
            or {}
        )

        checkout_id = (
            metadata.get("checkout_id")
            or metadata.get("lead_id")
            or payload.get("checkout_id")
            or payload.get("lead_id")
        )

        phone = (
            metadata.get("phone")
            or payload.get("phone")
            or payload.get("to")
            or payload.get("user_phone_number")
        )

        # 3. Fallback active checkout lookup by phone
        if not checkout_id and phone:
            formatted_phone = f"+{str(phone).lstrip('+')}"
            active_checkouts = await list_active_checkouts(formatted_phone)
            if active_checkouts:
                checkout_id = str(active_checkouts[0].id)

        if not checkout_id:
            logger.warning("Sarvam webhook ignored: Missing valid checkout_id or identifiable phone in payload.")
            return Response(status_code=200)

        summary = (
            payload.get("summary")
            or payload.get("transcript")
            or payload.get("call_summary")
            or payload.get("interaction_transcript")
        )

        formatted_phone = f"+{str(phone).lstrip('+')}" if phone else "unknown"

        # 4. Offload graph execution to BackgroundTasks to avoid HTTP timeouts
        background_tasks.add_task(
            append_voice_summary,
            thread_id=str(checkout_id),
            status=status or "unknown",
            phone=formatted_phone,
            summary=summary,
            raw=payload,
        )

        logger.info(f"Queued background processing for Sarvam voice webhook (checkout_id={checkout_id}, status={status})")

    except Exception as exc:
        logger.exception(f"Error processing Sarvam voice webhook payload: {exc}")

    # Always return HTTP 200 OK immediately
    return Response(status_code=200)