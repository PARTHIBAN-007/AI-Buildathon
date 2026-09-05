from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict
from loguru import logger

from src.config import get_settings
from src.infrastructure.clients.sarvam_client import SarvamClient
from src.jobs.celery_app import celery_app
from src.infrastructure.postgres.repository import (
    create_scheduled_job,
    get_checkout,
    get_checkout_by_razorpay_order_id,
    list_scheduled_jobs_for_checkout,
    set_scheduled_job_celery_id,
    update_scheduled_job_status,
)

settings = get_settings()

COOLDOWN_SECONDS = 7200
MAX_ATTEMPTS = 3


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sanitize_json_value(val: Any) -> Any:
    """Recursively converts Decimals into float/native JSON types."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, dict):
        return {k: _sanitize_json_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_json_value(v) for v in val]
    return val


def _extract_customer_name(checkout: Any, metadata: Dict[str, Any] | None = None) -> str:
    merged = metadata or {}

    for key in ("customer_name", "user_name", "customer", "name"):
        val = _get_val(merged, key)
        if val and str(val).strip().lower() not in ("customer", "user", "none", ""):
            return str(val).strip()

    if checkout:
        cart = getattr(checkout, "cart_items", None)
        if isinstance(cart, dict):
            name = cart.get("customer_name") or cart.get("user_name") or cart.get("name")
            if name and str(name).strip().lower() not in ("customer", "user", "none", ""):
                return str(name).strip()

    return "Customer"


def _extract_item_name(checkout: Any, metadata: Dict[str, Any] | None = None) -> str:
    merged = metadata or {}
    if merged.get("item_name"):
        return str(merged["item_name"]).strip()

    if checkout:
        cart = getattr(checkout, "cart_items", None)
        if isinstance(cart, list) and len(cart) > 0:
            item_names = [
                str(i.get("name") or i.get("title")).strip()
                for i in cart
                if isinstance(i, dict) and (i.get("name") or i.get("title"))
            ]
            if item_names:
                return ", ".join(item_names)
        elif isinstance(cart, dict):
            name = cart.get("name") or cart.get("title") or cart.get("item_name")
            if name:
                return str(name).strip()

    return "items in your cart"


class VoiceService:
    def __init__(self, client: SarvamClient | None = None) -> None:
        self.client = client or SarvamClient()

    async def _resolve_checkout_entity(self, identifier: str | None) -> Any:
        if not identifier or str(identifier).strip().lower() == "none":
            return None

        clean_id = str(identifier).strip()
        checkout = await get_checkout(clean_id)
        if not checkout and clean_id.startswith("order_"):
            checkout = await get_checkout_by_razorpay_order_id(clean_id)

        return checkout

    async def _cancel_pending_jobs(self, checkout_id: str) -> int:
        if not checkout_id:
            return 0

        jobs = await list_scheduled_jobs_for_checkout(checkout_id=str(checkout_id))
        cancelled_count = 0

        for job in jobs:
            status = _get_val(job, "status")
            if status in {"CANCELLED", "PAID", "COMPLETED", "FAILED"}:
                continue

            celery_task_id = _get_val(job, "celery_task_id")
            job_id = _get_val(job, "id")

            if celery_task_id:
                try:
                    celery_app.control.revoke(str(celery_task_id), terminate=True)
                    logger.info(f"Revoked Celery task {celery_task_id} for checkout_id={checkout_id}")
                except Exception as exc:
                    logger.warning(f"Failed to revoke Celery task {celery_task_id}: {exc}")

            if job_id:
                await update_scheduled_job_status(str(job_id), status="CANCELLED")
                cancelled_count += 1

        return cancelled_count

    async def _is_checkout_paid(self, checkout_id: str) -> bool:
        checkout = await self._resolve_checkout_entity(checkout_id)
        if not checkout:
            return False
        return _get_val(checkout, "status") == "PAID"

    async def _is_in_cooldown_or_max_attempts(self, checkout: Any) -> tuple[bool, str]:
        if not checkout:
            return False, "ok"

        attempts = _get_val(checkout, "call_attempt_count", 0) or 0
        if attempts >= MAX_ATTEMPTS:
            return True, "max_attempts_reached"

        last_called = _get_val(checkout, "last_call_triggered_at")
        if last_called:
            if last_called.tzinfo is None:
                last_called = last_called.replace(tzinfo=timezone.utc)

            elapsed = (datetime.now(timezone.utc) - last_called).total_seconds()
            if elapsed < COOLDOWN_SECONDS:
                return True, f"cooldown_active_{int(COOLDOWN_SECONDS - elapsed)}s_remaining"

        return False, "ok"

    async def _build_checkout_payload(
        self,
        phone: str | None,
        checkout: Any | None,
        checkout_id: str | None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        merged = dict(metadata or {})

        resolved_phone = (
            phone
            or _get_val(merged, "phone")
            or _get_val(merged, "customer_phone")
            or _get_val(checkout, "customer_phone")
            or ""
        )

        customer_name = _extract_customer_name(checkout, merged)
        item_name = _extract_item_name(checkout, merged)

        # Fallback order: amount_in_inr -> amount_inr -> DB total_amount
        raw_amount = (
            _get_val(merged, "amount_in_inr")
            if _get_val(merged, "amount_in_inr") is not None
            else _get_val(merged, "amount_inr")
        )
        if raw_amount is None and checkout:
            raw_amount = _get_val(checkout, "total_amount")

        amount_in_inr = float(raw_amount or 0.0)
        safe_checkout_id = str(_get_val(checkout, "id")) if checkout else (checkout_id or "")

        payload = {
            "checkout_id": safe_checkout_id,
            "phone": resolved_phone,
            "customer_name": customer_name,
            "item_name": item_name,
            "amount_in_inr": amount_in_inr,
        }

        return _sanitize_json_value(payload)

    async def schedule_call(
        self,
        phone: str,
        eta_seconds: int = 3600,
        checkout_id: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        checkout = await self._resolve_checkout_entity(checkout_id) if checkout_id else None
        db_checkout_id = str(_get_val(checkout, "id")) if checkout else checkout_id

        if db_checkout_id and await self._is_checkout_paid(db_checkout_id):
            await self._cancel_pending_jobs(db_checkout_id)
            return {"status": "cancelled", "reason": "payment_already_paid", "checkout_id": db_checkout_id}

        blocked, reason = await self._is_in_cooldown_or_max_attempts(checkout)
        if blocked:
            return {"status": "blocked", "reason": reason, "checkout_id": db_checkout_id}

        scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=int(eta_seconds))

        checkout_payload = await self._build_checkout_payload(
            phone=phone,
            checkout=checkout,
            checkout_id=db_checkout_id,
            metadata=metadata,
        )

        job = await create_scheduled_job(
            checkout_id=db_checkout_id,
            phone=checkout_payload["phone"],
            celery_task_id=None,
            job_type="voice",
            status="SCHEDULED",
            scheduled_at=scheduled_time,
        )

        job_id = _get_val(job, "id")

        task = celery_app.send_task(
            "tasks.trigger_sarvam_voice_call",
            args=[checkout_payload["phone"], checkout_payload],
            countdown=int(eta_seconds),
            expires=180,
        )

        celery_id = getattr(task, "id", None)
        if celery_id and job_id:
            await set_scheduled_job_celery_id(str(job_id), celery_id)

        return {
            "job_id": str(job_id) if job_id else None,
            "checkout_id": db_checkout_id,
            "task_id": celery_id,
            "scheduled_at": scheduled_time.isoformat(),
        }

    async def reschedule_call(
        self,
        checkout_id: str,
        new_eta_seconds: int,
        phone: str | None = None,
    ) -> Dict[str, Any]:
        checkout = await self._resolve_checkout_entity(checkout_id)
        if not checkout:
            raise KeyError(f"Checkout record not found for '{checkout_id}'.")

        db_checkout_id = str(_get_val(checkout, "id"))

        if await self._is_checkout_paid(db_checkout_id):
            await self._cancel_pending_jobs(db_checkout_id)
            return {"status": "cancelled", "reason": "payment_already_paid", "checkout_id": db_checkout_id}

        blocked, reason = await self._is_in_cooldown_or_max_attempts(checkout)
        if blocked:
            return {"status": "blocked", "reason": reason, "checkout_id": db_checkout_id}

        await self._cancel_pending_jobs(db_checkout_id)
        scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=int(new_eta_seconds))

        payload = await self._build_checkout_payload(
            phone=phone,
            checkout=checkout,
            checkout_id=db_checkout_id,
        )

        job = await create_scheduled_job(
            checkout_id=db_checkout_id,
            phone=payload["phone"],
            celery_task_id=None,
            job_type="voice",
            status="SCHEDULED",
            scheduled_at=scheduled_time,
        )

        job_id = _get_val(job, "id")

        task = celery_app.send_task(
            "tasks.trigger_sarvam_voice_call",
            args=[payload["phone"], payload],
            countdown=int(new_eta_seconds),
            expires=180,
        )

        celery_id = getattr(task, "id", None)
        if celery_id and job_id:
            await set_scheduled_job_celery_id(str(job_id), celery_id)

        return {
            "job_id": str(job_id) if job_id else None,
            "checkout_id": db_checkout_id,
            "task_id": celery_id,
            "scheduled_at": scheduled_time.isoformat(),
        }

    async def trigger_immediate_call(
        self, phone: str | None = None, checkout_id: str | None = None, metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        checkout = await self._resolve_checkout_entity(checkout_id) if checkout_id else None
        db_checkout_id = str(_get_val(checkout, "id")) if checkout else checkout_id

        if db_checkout_id and await self._is_checkout_paid(db_checkout_id):
            await self._cancel_pending_jobs(db_checkout_id)
            return {"status": "cancelled", "reason": "payment_already_paid", "checkout_id": db_checkout_id}

        blocked, reason = await self._is_in_cooldown_or_max_attempts(checkout)
        if blocked:
            return {"status": "blocked", "reason": reason, "checkout_id": db_checkout_id}

        if db_checkout_id:
            await self._cancel_pending_jobs(db_checkout_id)

        checkout_payload = await self._build_checkout_payload(
            phone=phone,
            checkout=checkout,
            checkout_id=db_checkout_id,
            metadata=metadata,
        )

        job = await create_scheduled_job(
            checkout_id=db_checkout_id,
            phone=checkout_payload["phone"],
            celery_task_id=None,
            job_type="voice",
            status="SCHEDULED",
        )

        job_id = _get_val(job, "id")

        task = celery_app.send_task(
            "tasks.trigger_sarvam_voice_call",
            args=[checkout_payload["phone"], checkout_payload],
            expires=180,
        )

        celery_id = getattr(task, "id", None)
        if celery_id and job_id:
            await set_scheduled_job_celery_id(str(job_id), celery_id)

        return {
            "task_id": celery_id,
            "job_id": str(job_id) if job_id else None,
            "checkout_id": db_checkout_id,
        }

    async def cancel_call(self, checkout_id: str) -> bool:
        checkout = await self._resolve_checkout_entity(checkout_id)
        db_checkout_id = str(_get_val(checkout, "id")) if checkout else checkout_id

        if not db_checkout_id:
            return False

        cancelled_count = await self._cancel_pending_jobs(db_checkout_id)
        return cancelled_count > 0