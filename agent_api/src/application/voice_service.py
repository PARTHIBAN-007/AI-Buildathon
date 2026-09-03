from __future__ import annotations

from typing import Any, Dict
from datetime import datetime
from loguru import logger

from src.config import get_settings
from src.infrastructure.clients.sarvam_client import SarvamClient
from src.jobs.celery_app import celery_app
from src.infrastructure.postgres.repository import (
    create_scheduled_job,
    update_scheduled_job_status,
    set_scheduled_job_celery_id,
    get_scheduled_job,
    list_scheduled_jobs_for_checkout,
)

settings = get_settings()

class VoiceService:
    def __init__(self, client: SarvamClient | None = None) -> None:
        self.client = client or SarvamClient()

    async def _cancel_all_pending_jobs_for_checkout(self, checkout_id: str | None = None, phone: str | None = None) -> int:
        jobs = await list_scheduled_jobs_for_checkout(checkout_id=checkout_id, phone=phone)
        cancelled = 0
        for job in jobs:
            if job.status in {"CANCELLED", "PAID", "COMPLETED", "FAILED"}:
                continue
            if job.celery_task_id:
                try:
                    celery_app.control.revoke(job.celery_task_id, terminate=True)
                except Exception:
                    logger.warning(f"Failed to revoke existing task {job.celery_task_id}")
            job.status = "CANCELLED"
            job.updated_at = datetime.utcnow()
                # persist status change using repository helper
            await update_scheduled_job_status(job.id, status="CANCELLED")
            cancelled += 1
            return cancelled

    async def _checkout_is_paid(self, checkout_id: str | None = None, phone: str | None = None) -> bool:
        if checkout_id is None and phone is None:
            return False
        if checkout_id is not None:
            try:
                from src.infrastructure.postgres.repository import get_checkout
                checkout = await get_checkout(checkout_id)
                if checkout and checkout.status == "PAID":
                    return True
            except Exception:
                logger.warning(f"Unable to load checkout {checkout_id} while checking payment status")
        if phone is not None:
            try:
                from src.infrastructure.postgres.repository import list_checkouts_by_phone
                checkouts = await list_checkouts_by_phone(phone)
                if any(item.status == "PAID" for item in checkouts):
                    return True
            except Exception:
                logger.warning(f"Unable to load phone checkouts for {phone} while checking payment status")
        return False

    async def trigger_call(self, phone: str, language: str | None = None, metadata: Dict | None = None) -> Dict[str, Any]:
        logger.info(f"VoiceService.trigger_call phone={phone}")
        # map common metadata keys into Sarvam client parameters
        return await self.client.trigger_call(
            phone,
            checkout_id=(metadata or {}).get("checkout_id"),
            call_summary=(metadata or {}).get("call_summary"),
            opening_line=(metadata or {}).get("opening_line"),
            user_name=(metadata or {}).get("user_name"),
            connection_id=(metadata or {}).get("connection_id") or getattr(settings, "EXOTEL_ACCOUNT_SID", None),
            agent_phone_number=(metadata or {}).get("agent_phone_number") or getattr(settings, "EXOTEL_PHONE_NUMBER", None),
            webhook_url=(metadata or {}).get("webhook_url"),
            lead_id=(metadata or {}).get("lead_id"),
        )

    async def trigger_immediate_call(self, phone: str, checkout_id: str | None = None, metadata: Dict | None = None) -> Dict[str, Any]:
        """Trigger an immediate voice call and record it in ScheduledJob as RUNNING."""
        logger.info(f"VoiceService.trigger_immediate_call phone={phone}")
        if await self._checkout_is_paid(checkout_id=checkout_id, phone=phone):
            await self._cancel_all_pending_jobs_for_checkout(checkout_id=checkout_id, phone=phone)
            return {"status": "cancelled", "reason": "payment_already_paid"}
        job = await create_scheduled_job(checkout_id=checkout_id, celery_task_id=None, job_type="voice", status="SCHEDULED")
        payload = {"checkout_id": checkout_id, **(metadata or {})}
        task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=[phone, payload])
        celery_id = getattr(task, "id", None)
        await update_scheduled_job_status(job.id, status="SCHEDULED")
        job_record = await get_scheduled_job(job.id)
        if job_record:
            await set_scheduled_job_celery_id(job.id, celery_id)
        return {"task_id": celery_id, "job_id": job.id}

    async def schedule_call(self, phone: str, eta_seconds: int = 7200, checkout_id: str | None = None, metadata: Dict | None = None) -> dict:
        logger.info(f"VoiceService.schedule_call phone={phone} eta={eta_seconds}")
        if await self._checkout_is_paid(checkout_id=checkout_id, phone=phone):
            await self._cancel_all_pending_jobs_for_checkout(checkout_id=checkout_id, phone=phone)
            return {"status": "cancelled", "reason": "payment_already_paid"}
        job = await create_scheduled_job(checkout_id=checkout_id, celery_task_id=None, job_type="voice", status="SCHEDULED")
        payload = {"checkout_id": checkout_id, **(metadata or {})}
        task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=[phone, payload], countdown=eta_seconds)
        celery_id = getattr(task, "id", None)
        job_record = await get_scheduled_job(job.id)
        if job_record:
            await set_scheduled_job_celery_id(job.id, celery_id)
        return {"job_id": job.id, "task_id": celery_id}

    async def reschedule_call(self, job_id: str, new_eta_seconds: int) -> dict:
        logger.info(f"VoiceService.reschedule_call job={job_id} new_eta={new_eta_seconds}")
        job = await get_scheduled_job(job_id)
        if job is None:
            raise KeyError("Scheduled job not found")
        if await self._checkout_is_paid(checkout_id=job.checkout_id, phone=job.phone):
            await self._cancel_all_pending_jobs_for_checkout(checkout_id=job.checkout_id, phone=job.phone)
            return {"status": "cancelled", "reason": "payment_already_paid"}
        if job.celery_task_id:
            try:
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception:
                logger.warning(f"Failed to revoke existing task {job.celery_task_id}")
        payload = {"checkout_id": job.checkout_id}
        task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=[job.phone or job.checkout_id or "placeholder", payload], countdown=new_eta_seconds)
        celery_id = getattr(task, "id", None)
        await set_scheduled_job_celery_id(job.id, celery_id)
        return {"job_id": job.id, "task_id": celery_id}

    async def cancel_call(self, job_id: str) -> bool:
        logger.info(f"VoiceService.cancel_call job={job_id}")
        job = await get_scheduled_job(job_id)
        if job is None:
            return False
        if job.celery_task_id:
            try:
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception:
                logger.warning(f"Failed to revoke existing task {job.celery_task_id}")
        await update_scheduled_job_status(job.id, status="CANCELLED")
        return True
