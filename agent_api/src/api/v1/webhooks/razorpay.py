from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from src.config import get_settings
from src.services.recovery_service import handle_razorpay_webhook

router = APIRouter()


@router.post("/razorpay")
async def razorpay_webhook(request: Request):
    settings = get_settings()
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    try:
        payload = await request.json()
    except Exception:
        payload = None

    try:
        await handle_razorpay_webhook(payload, raw, signature)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error handling razorpay webhook: {}", exc)
        raise HTTPException(status_code=500, detail="Webhook processing failed")
