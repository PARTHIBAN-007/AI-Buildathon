from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import HTTPException
from loguru import logger

from src.application.customer_service import build_customer_profile
from src.application.voice_service import VoiceService
from src.infrastructure.clients.whatsapp_client import WhatsAppClient
from src.jobs.celery_app import celery_app
from src.infrastructure.postgres.repository import (
    list_active_checkouts,
    list_scheduled_jobs_for_checkout,
    load_agent_state,
    save_agent_state,
    update_checkout_status,
    update_scheduled_job_status,
    upsert_checkout,
)


def _extract_payload_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts order_id, payment_link_id, checkout_id, phone, amount, and notes from Razorpay payload."""
    p = payload.get("payload", {})
    payment = p.get("payment", {}).get("entity", {})
    order = p.get("order", {}).get("entity", {})
    payment_link = p.get("payment_link", {}).get("entity", {})

    notes = payment.get("notes") or order.get("notes") or payment_link.get("notes") or {}

    order_id = payment.get("order_id") or order.get("id")
    payment_link_id = payment.get("payment_link_id") or payment_link.get("id")
    internal_checkout_id = notes.get("checkout_id")

    phone = (
        payment.get("contact")
        or payment_link.get("customer", {}).get("contact")
        or notes.get("phone")
        or notes.get("customer_phone")
    )

    raw_amount = payment.get("amount") or order.get("amount") or payment_link.get("amount", 0)
    amount_inr = int(raw_amount / 100) if raw_amount else 0

    customer_name = (
        notes.get("customer_name")
        or payment.get("name")
        or payment_link.get("customer", {}).get("name")
        or payment.get("email")
        or "Customer"
    )

    item_name = (
        notes.get("item_name")
        or notes.get("items")
        or notes.get("product_name")
        or "items in your cart"
    )

    error_desc = payment.get("error_description", "Payment failed or was cancelled.")

    return {
        "order_id": order_id,
        "payment_link_id": payment_link_id,
        "checkout_id": internal_checkout_id,
        "payment_id": payment.get("id"),
        "phone": phone,
        "amount_inr": amount_inr,
        "amount_in_inr": amount_inr,
        "customer_name": customer_name,
        "item_name": item_name,
        "error_desc": error_desc,
        "notes": notes,
    }


async def _sync_payment_success_to_agent_memory(
    checkout_id: str, phone: str, amount_inr: int, order_id: Optional[str]
) -> None:
    """Updates agent state to PAID in DB so future WhatsApp replies acknowledge successful payment."""
    thread_id = str(checkout_id)

    current_state = await load_agent_state(thread_id) or {}

    current_state["payment_status"] = "PAID"
    current_state["is_resolved"] = True

    messages = current_state.get("messages", [])
    confirmation_text = (
        f"Payment Confirmed! We received ₹{amount_inr} for Order #{order_id or checkout_id}. "
        "Thank you for your purchase!"
    )

    messages.append({"role": "system", "content": f"System Event: Payment of ₹{amount_inr} received successfully."})
    messages.append({"role": "assistant", "content": confirmation_text})
    current_state["messages"] = messages

    await save_agent_state(thread_id, current_state)

    if phone and phone != "UNKNOWN":
        try:
            logger.info(f"Sent WhatsApp payment success notification to {phone}")
        except Exception as exc:
            logger.exception(f"Failed to send WhatsApp success message to {phone}: {exc}")


async def handle_razorpay_webhook(
    payload: Dict[str, Any] | None, raw: bytes | None, signature: str | None
) -> None:
    if not payload:
        return

    event_type = payload.get("event") or payload.get("type", "")
    meta = _extract_payload_metadata(payload)

    # 1. HANDLE PAYMENT SUCCESS (PAID)
    is_success_event = event_type in ("payment.captured", "order.paid", "payment_link.paid")

    if is_success_event:
        logger.info(f"Processing PAID event for checkout_id={meta['checkout_id']}, phone={meta['phone']}")

        checkout = await upsert_checkout(
            checkout_id=meta["checkout_id"],
            razorpay_order_id=meta["order_id"],
            razorpay_payment_link_id=meta["payment_link_id"],
            customer_phone=meta["phone"] or "UNKNOWN",
            total_amount=meta["amount_inr"],
            status="PAID",
        )

        if checkout:
            await cancel_checkout_recovery(checkout_id=str(checkout.id))
            await _sync_payment_success_to_agent_memory(
                checkout_id=str(checkout.id),
                phone=meta["phone"],
                amount_inr=meta["amount_inr"],
                order_id=meta["order_id"],
            )
        return

    # 2. HANDLE PAYMENT FAILURE (FAILED)
    if event_type != "payment.failed":
        logger.info(f"Razorpay event '{event_type}' is non-actionable; ignoring.")
        return

    if not meta["phone"]:
        logger.error(f"Cannot process payment failure for order_id={meta['order_id']}: Customer phone missing.")
        return

    checkout = await upsert_checkout(
        checkout_id=meta["checkout_id"],
        razorpay_order_id=meta["order_id"],
        razorpay_payment_link_id=meta["payment_link_id"],
        customer_phone=meta["phone"],
        total_amount=meta["amount_inr"],
        status="FAILED",
    )

    try:
        profile = await build_customer_profile(meta["phone"])
    except Exception as exc:
        logger.exception(f"Failed to build customer profile for {meta['phone']}: {exc}")
        profile = {"summary": "No profile available", "max_discount": 0}

    context = {
        "checkout_id": str(checkout.id),
        "order_id": meta["order_id"],
        "payment_link_id": meta["payment_link_id"],
        "payment_id": meta["payment_id"],
        "amount_inr": meta["amount_inr"],
        "amount_in_inr": meta["amount_inr"],
        "failure_reason": meta["error_desc"],
        "customer_phone": meta["phone"],
        "customer_name": meta.get("customer_name") or "Customer",
        "item_name": meta.get("item_name") or "items in your cart",
        "customer_profile": profile,
        "payment_status": "FAILED",
    }

    try:
        voice_service = VoiceService()
        await voice_service.schedule_call(
            phone=meta["phone"],
            eta_seconds=60,
            checkout_id=str(checkout.id),
            metadata=context,
        )
    except Exception as exc:
        logger.exception(f"Failed to schedule voice call for checkout_id={checkout.id}: {exc}")

    try:
        from src.agent.graph import start_agent_thread
        await start_agent_thread(thread_id=str(checkout.id), context=context)
    except Exception as exc:
        logger.exception(f"Failed to start agent thread for checkout_id={checkout.id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to start recovery agent thread")


async def cancel_checkout_recovery(checkout_id: str) -> None:
    """Cancels pending recovery jobs and revokes Celery tasks tied to a checkout."""
    logger.info(f"Cancelling recovery tasks for checkout_id: {checkout_id}")

    jobs = await list_scheduled_jobs_for_checkout(checkout_id=checkout_id)

    for job in jobs:
        status = getattr(job, "status", None) or (job.get("status") if isinstance(job, dict) else None)
        if status in {"PENDING", "SCHEDULED"}:
            job_id = getattr(job, "id", None) or (job.get("id") if isinstance(job, dict) else None)
            celery_task_id = getattr(job, "celery_task_id", None) or (job.get("celery_task_id") if isinstance(job, dict) else None)

            if job_id:
                await update_scheduled_job_status(job_id=str(job_id), status="CANCELLED")

            if celery_task_id:
                try:
                    celery_app.control.revoke(str(celery_task_id), terminate=True)
                    logger.info(f"Revoked Celery task {celery_task_id} for job {job_id}")
                except Exception as exc:
                    logger.warning(f"Could not revoke Celery task {celery_task_id}: {exc}")


async def lookup_active_checkouts(customer_phone: str) -> list:
    """Retrieves all non-PAID / non-CANCELLED checkouts for a given customer phone."""
    return await list_active_checkouts(customer_phone)


async def mark_checkout_paid(checkout_id: str) -> None:
    """Marks checkout as PAID, syncs memory, and revokes pending recovery tasks."""
    checkout = await update_checkout_status(checkout_id, status="PAID")
    if checkout is None:
        raise HTTPException(status_code=404, detail="Checkout not found")

    await cancel_checkout_recovery(checkout_id=checkout_id)
    await _sync_payment_success_to_agent_memory(
        checkout_id=str(checkout.id),
        phone=checkout.customer_phone,
        amount_inr=int(checkout.total_amount),
        order_id=checkout.razorpay_order_id,
    )