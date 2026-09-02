from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from loguru import logger

from src.agent.graph import start_agent_thread
from src.application.customer_service import build_customer_profile
from src.infrastructure.postgres.repository import list_active_checkouts as _list_active_checkouts
from src.infrastructure.postgres.repository import update_checkout_status


def _extract_phone_from_razorpay(payload: Dict[str, Any] | None) -> str | None:
    """Best-effort extraction of customer phone number from Razorpay webhook payload.

    Razorpay payload formats vary. Common places to look:
    - payload['payload']['payment']['entity']['contact']
    - payload['payload']['order']['entity']['notes'] (if merchant stored phone)
    - payload['payload']['payment']['entity']['contact']
    """
    if not payload:
        return None
    try:
        p = payload.get("payload", {})
        # payment entity
        payment = p.get("payment", {}).get("entity")
        if payment:
            contact = payment.get("contact")
            if contact:
                return contact
        order = p.get("order", {}).get("entity")
        if order:
            notes = order.get("notes") or {}
            # merchant may store phone in notes['phone']
            phone = notes.get("phone") or notes.get("customer_phone")
            if phone:
                return phone
    except Exception:
        logger.warning("Unable to extract phone from Razorpay payload")
    return None


async def handle_razorpay_webhook(payload: Dict[str, Any] | None, raw: bytes | None, signature: str | None) -> None:
    logger.info(f"Handling razorpay webhook payload: {payload}")

    event_type = None
    if payload:
        event_type = payload.get("event") or payload.get("type")

    # Detect payment failed event
    is_payment_failed = False
    try:
        if event_type and "payment.failed" in event_type:
            is_payment_failed = True
        else:
            # sometimes payload contains nested structure
            p = (payload or {}).get("payload", {})
            payment_entity = p.get("payment", {}).get("entity") if p else None
            if payment_entity and payment_entity.get("status") == "failed":
                is_payment_failed = True
    except Exception:
        logger.warning("Could not determine event type from payload")

    if not is_payment_failed:
        logger.info("Razorpay webhook received but not a payment.failed event; ignoring for agent startup")
        return

    # Extract phone
    phone = _extract_phone_from_razorpay(payload)
    if not phone:
        # If phone is missing, cannot start phone-based recovery thread
        logger.error("Razorpay payment.failed received but customer phone could not be determined")
        raise HTTPException(status_code=400, detail="customer phone not found in webhook payload")

    # Build customer profile
    try:
        profile = await build_customer_profile(phone)
    except Exception as exc:
        logger.exception(f"Failed to build customer profile for {phone}: {exc}")
        profile = {"summary": "No profile available", "max_discount": 0}

    # Compose context for agent: include failure reason, any order or payment details, and customer profile
    context = {
        "failure_reason": "payment.failed from Razorpay",
        "customer_phone": phone,
        "payment_payload": payload,
        "customer_profile": profile,
    }

    # Start agent Turn 0 for recovery
    try:
        await start_agent_thread(thread_id=phone, context=context)
    except Exception as exc:
        logger.exception(f"Failed to start agent thread for {phone}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to start recovery agent")

    return


async def lookup_active_checkouts(customer_phone: str) -> list:
    logger.info(f"Lookup active checkouts for {customer_phone}")
    return await _list_active_checkouts(customer_phone)


async def mark_checkout_paid(checkout_id: str) -> None:
    logger.info(f"Marking checkout {checkout_id} as PAID")
    checkout = await update_checkout_status(checkout_id, status="PAID")
    if checkout is None:
        raise HTTPException(status_code=404, detail="Checkout not found")
    return
