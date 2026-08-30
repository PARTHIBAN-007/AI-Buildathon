from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from src.application.payment_service import PaymentService

router = APIRouter(prefix="", tags=["Payments"])


class CreateOrderRequest(BaseModel):
    amount_in_inr: int
    receipt: str | None = None


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/create-order")
async def create_order(payload: CreateOrderRequest) -> dict:
    if payload.amount_in_inr <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    service = PaymentService()
    try:
        return service.create_order(amount_in_inr=payload.amount_in_inr, receipt=payload.receipt)
    except ValueError as exc:
        logger.warning("Invalid Razorpay order request: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to create Razorpay order: {}", exc)
        raise HTTPException(status_code=502, detail="Payment API error") from exc


@router.post("/verify-payment")
async def verify_payment(payload: VerifyPaymentRequest) -> dict:
    service = PaymentService()
    try:
        is_valid = service.verify_payment(
            razorpay_order_id=payload.razorpay_order_id,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail="Payment signature verification failed")

        return {
            "verified": True,
            "message": "Payment verified successfully",
            "order_id": payload.razorpay_order_id,
            "payment_id": payload.razorpay_payment_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Payment verification failed: {}", exc)
        raise HTTPException(status_code=400, detail="Payment verification failed") from exc


@router.post("/payment-failed")
async def payment_failed(payload: dict) -> dict:
    logger.error("Razorpay payment failed response: {}", payload)
    return {
        "status": "failed",
        "message": "Payment failure captured",
        "payload": payload,
    }


@router.post("/razorpay-webhook")
async def razorpay_webhook(request: Request) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature header")

    service = PaymentService()
    try:
        is_valid = service.verify_webhook(payload=raw_body, signature=signature)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

        payload = await request.json()
        logger.info("Received Razorpay webhook payload: {}", payload)
        return {"status": "ok", "received": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Razorpay webhook processing failed: {}", exc)
        raise HTTPException(status_code=400, detail="Razorpay webhook processing failed") from exc
