from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.services.recovery_service import mark_checkout_paid, lookup_active_checkouts

router = APIRouter()


class PaymentStatusRequest(BaseModel):
    customer_phone: str


@router.post("/cart/checkouts/by-phone")
async def check_checkouts(payload: PaymentStatusRequest):
    try:
        items = await lookup_active_checkouts(payload.customer_phone)
        return {"status": "ok", "checkouts": items}
    except Exception as exc:
        logger.exception("Failed to query checkouts: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to query checkouts")


class MarkPaidRequest(BaseModel):
    checkout_id: str


@router.post("/cart/mark-paid")
async def mark_paid(payload: MarkPaidRequest):
    try:
        await mark_checkout_paid(payload.checkout_id)
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Failed to mark checkout paid: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to mark paid")
