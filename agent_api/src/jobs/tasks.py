from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from loguru import logger

from src.infrastructure.clients.sarvam_client import SarvamClient
from src.infrastructure.postgres.core import SessionLocal
from src.infrastructure.postgres.models import Checkout
from src.jobs.celery_app import celery_app

COOLDOWN_SECONDS = 7200
MAX_ATTEMPTS = 3


def _extract_item_name_from_cart(cart: Any) -> str | None:
    if isinstance(cart, list) and len(cart) > 0:
        names = []
        for item in cart:
            if isinstance(item, dict):
                name = item.get("name") or item.get("title") or item.get("item_name")
                if name:
                    names.append(str(name).strip())
            elif isinstance(item, str) and item.strip():
                names.append(item.strip())
        if names:
            return ", ".join(names)
    elif isinstance(cart, dict):
        name = cart.get("name") or cart.get("title") or cart.get("item_name")
        if name:
            return str(name).strip()
    return None


@celery_app.task(name="tasks.trigger_sarvam_voice_call")
def trigger_sarvam_voice_call(phone: str, payload: dict | None = None) -> dict:
    """Trigger an outbound Sarvam voice call with database-backed variable enrichment."""
    logger.info(f"Triggering Sarvam voice call task for phone={phone} with payload={payload}")

    logger.error(payload)

    if not phone:
        logger.warning("No phone number provided for Sarvam voice task; skipping.")
        return {"status": "skipped", "reason": "missing_phone"}


    p = dict(payload or {})
    checkout_id = p.get("checkout_id")

    customer_name = p.get("customer_name")
    amount_in_inr = p.get("amount_in_inr") if p.get("amount_in_inr") is not None else p.get("amount_inr")
    item_name = p.get("item_name")

    # DB VALIDATION & ENRICHMENT
    if checkout_id:
        with SessionLocal() as session:
            checkout = session.get(Checkout, str(checkout_id))
            if not checkout:
                logger.warning(f"Checkout {checkout_id} not found in DB; skipping call.")
                return {"status": "skipped", "reason": "checkout_not_found"}

            if checkout.status == "PAID":
                logger.info(f"Checkout {checkout_id} is already PAID; skipping call.")
                return {"status": "skipped", "reason": "already_paid"}

            attempts = checkout.call_attempt_count or 0
            if attempts >= MAX_ATTEMPTS:
                logger.warning(f"Checkout {checkout_id} reached max call attempts ({attempts}); skipping.")
                return {"status": "skipped", "reason": "max_attempts_reached"}

            last_called = checkout.last_call_triggered_at
            if last_called:
                if last_called.tzinfo is None:
                    last_called = last_called.replace(tzinfo=timezone.utc)

                elapsed = (datetime.now(timezone.utc) - last_called).total_seconds()
                if elapsed < COOLDOWN_SECONDS:
                    logger.warning(f"Checkout {checkout_id} call blocked by cooldown; skipping.")
                    return {"status": "skipped", "reason": "cooldown_active"}

            # DB Amount Fallback
            if (amount_in_inr is None or float(amount_in_inr or 0) == 0.0) and checkout.total_amount is not None:
                amount_in_inr = float(checkout.total_amount)

            if not item_name and checkout.cart_items:
                item_name = _extract_item_name_from_cart(checkout.cart_items)

            # Update tracking counters
            checkout.call_attempt_count = attempts + 1
            checkout.last_call_triggered_at = datetime.now(timezone.utc)
            session.commit()

    async def _execute_call() -> dict:
        client = SarvamClient()
        try:
            return await client.trigger_call(
                phone=phone,
                checkout_id=checkout_id,
                customer_name=customer_name,
                amount_in_inr=amount_in_inr,
                item_name=item_name,
                webhook_url=p.get("webhook_url"),
            )
        finally:
            await client.close()

    try:
        return asyncio.run(_execute_call())
    except Exception as exc:
        logger.exception(f"Sarvam call execution failed for phone={phone}: {exc}")
        return {"status": "error", "error": str(exc)}