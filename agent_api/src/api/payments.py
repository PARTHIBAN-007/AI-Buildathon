from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger
from typing import Dict, Any

from src.application.recovery_service import mark_checkout_paid, lookup_active_checkouts
from src.application.payment_service import PaymentService

router = APIRouter()


class PaymentStatusRequest(BaseModel):
    customer_phone: str


@router.post("/cart/checkouts/by-phone")
async def check_checkouts(payload: PaymentStatusRequest):
    try:
        items = await lookup_active_checkouts(payload.customer_phone)
        return {"status": "ok", "checkouts": items}
    except Exception as exc:
        logger.exception(f"Failed to query checkouts: {exc}")
        raise HTTPException(status_code=500, detail="Failed to query checkouts")


class MarkPaidRequest(BaseModel):
    checkout_id: str


@router.post("/cart/mark-paid")
async def mark_paid(payload: MarkPaidRequest):
    try:
        await mark_checkout_paid(payload.checkout_id)
        return {"status": "ok"}
    except Exception as exc:
        logger.exception(f"Failed to mark checkout paid: {exc}")
        raise HTTPException(status_code=500, detail="Failed to mark paid")


class CreateOrderRequest(BaseModel):
    amount_in_inr: int
    receipt: str | None = None
    description: str | None = None
    customer: Dict[str, Any] | None = None
    checkout_id: str | None = None


from src.config import get_settings


@router.post("/payments/create-order")
async def create_order(payload: CreateOrderRequest):
    service = PaymentService()
    settings = get_settings()
    try:
        logger.info(
            f"Creating Razorpay order for amount={payload.amount_in_inr} receipt={payload.receipt} customer={payload.customer}"
        )
        order = await service.create_order(
            amount_in_inr=payload.amount_in_inr,
            receipt=payload.receipt,
            customer=payload.customer,
        )
        # return order info to UI (order.id, amount, currency etc.) and include publishable key
        key_id = getattr(settings, "RAZORPAY_API_KEY", None)
        return {"status": "ok", "key_id": key_id, "order": order}
    except Exception as exc:
        logger.exception(f"Failed to create order: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create order")


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    checkout_id: str | None = None


@router.post("/payments/verify")
async def verify_payment(payload: VerifyPaymentRequest):
    service = PaymentService()
    try:
        verified = service.verify_payment_signature(
            razorpay_order_id=payload.razorpay_order_id,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )

        if verified and payload.checkout_id:
            # mark internal checkout as paid
            await mark_checkout_paid(payload.checkout_id)

        return {"status": "ok", "verified": bool(verified)}
    except Exception as exc:
        logger.exception(f"Failed to verify payment: {exc}")
        raise HTTPException(status_code=500, detail="Failed to verify payment")
