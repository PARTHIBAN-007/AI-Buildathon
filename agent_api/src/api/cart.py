from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.config import get_settings
from src.application.customer_service import build_customer_profile
from src.agent.graph import start_agent_thread

router = APIRouter()


class CartItem(BaseModel):
    product_id: str
    title: str
    price: float
    qty: int


class AbandonedCartRequest(BaseModel):
    customer_phone: str
    cart_items: list[CartItem]
    total_amount: float
    reason: str | None = None


@router.post("/cart/abandoned")
async def cart_abandoned(payload: AbandonedCartRequest):
    settings = get_settings()
    logger.info(f"Received abandoned cart for {payload.customer_phone} amount={payload.total_amount}")

    try:
        profile = await build_customer_profile(payload.customer_phone)
    except Exception as exc:
        logger.warning(f"Customer profiling failed: {exc}")
        profile = {"summary": "No profile available", "max_discount": 0}

    # Start agent thread (Turn 0) with context
    try:
        context = {
            "failure_reason": payload.reason,
            "cart_items": [item.dict() for item in payload.cart_items],
            "total_amount": payload.total_amount,
            "customer_profile": profile,
        }
        await start_agent_thread(thread_id=payload.customer_phone, context=context)
    except Exception as exc:
        logger.exception(f"Failed to start agent thread: {exc}")
        raise HTTPException(status_code=500, detail="Agent initialization failed")

    return {"status": "ok", "message": "Abandoned cart recorded and recovery worker started"}
