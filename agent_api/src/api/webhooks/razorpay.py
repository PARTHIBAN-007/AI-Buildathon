from typing import Set
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from loguru import logger

from src.application.recovery_service import handle_razorpay_webhook
from src.infrastructure.clients.razorpay_client import RazorpayClient

router = APIRouter()

PROCESSED_EVENT_KEYS: Set[str] = set()


async def safe_handle_razorpay_webhook(payload: dict, raw: bytes, signature: str) -> None:
    """Wrapper to prevent unhandled background execution exceptions from crashing the event loop."""
    try:
        await handle_razorpay_webhook(payload, raw, signature)
    except Exception as exc:
        logger.exception(f"Background recovery execution failed: {exc}")


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_razorpay_signature: str = Header(default="", alias="x-razorpay-signature"),
):
    raw_body = await request.body()

    client = RazorpayClient()
    # if not client.verify_webhook_signature(raw_body, x_razorpay_signature):
    #     logger.warning("Unauthorized Razorpay webhook signature attempt.")
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    p_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    p_link_entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
    
    entity_id = p_entity.get("id") or p_link_entity.get("id")
    event_type = payload.get("event", "unknown")
    
    dedupe_key = f"{event_type}:{entity_id}" if entity_id else f"{event_type}:{payload.get('created_at')}"

    if dedupe_key in PROCESSED_EVENT_KEYS:
        logger.info(f"Duplicate webhook event ignored: {dedupe_key}")
        return {"status": "ignored", "reason": "duplicate_event"}

    PROCESSED_EVENT_KEYS.add(dedupe_key)

    background_tasks.add_task(safe_handle_razorpay_webhook, payload, raw_body, x_razorpay_signature)

    return {"status": "ok"}