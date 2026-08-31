from __future__ import annotations

from loguru import logger

from src.application.whatsapp_service import WhatsAppService
from src.application.payment_service import PaymentService
from src.application.voice_service import VoiceService
from src.jobs.celery_app import celery_app


whatsapp = WhatsAppService()
payment = PaymentService()
voice = VoiceService()


async def send_whatsapp_message(thread_id: str, text: str, buttons: list | None = None) -> dict:
    logger.info("Tool: send_whatsapp_message to %s", thread_id)
    # buttons are provider-specific; convert to template components at call site if needed
    return await whatsapp.send_text_message(to=thread_id, body=text)


async def generate_discounted_payment_link(thread_id: str, amount_in_inr: int, discount_pct: float = 0.0) -> dict:
    logger.info("Tool: generate_discounted_payment_link for %s discount=%s", thread_id, discount_pct)
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError("discount_pct must be between 0 and 100")
    discounted = max(1, int(amount_in_inr * (1 - discount_pct / 100.0)))
    return await payment.create_payment_link(amount_in_inr=discounted, description=f"Discounted for {thread_id}")


def schedule_voice_call(thread_id: str, eta_seconds: int = 7200) -> str:
    logger.info("Tool: schedule_voice_call for %s in %ss", thread_id, eta_seconds)
    task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=[thread_id], countdown=eta_seconds)
    return getattr(task, "id", "")


def reschedule_voice_call(celery_task_id: str, new_eta_seconds: int) -> str:
    logger.info("Tool: reschedule_voice_call %s to in %ss", celery_task_id, new_eta_seconds)
    try:
        celery_app.control.revoke(celery_task_id, terminate=True)
    except Exception:
        logger.warning("Failed to revoke existing task %s (it may not exist)", celery_task_id)
    task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=["placeholder"], countdown=new_eta_seconds)
    return getattr(task, "id", "")


def cancel_recovery_workflow(celery_task_id: str) -> bool:
    logger.info("Tool: cancel_recovery_workflow %s", celery_task_id)
    try:
        celery_app.control.revoke(celery_task_id, terminate=True)
        return True
    except Exception:
        logger.exception("Failed to revoke task %s", celery_task_id)
        return False


async def verify_payment_status(order_id: str) -> dict:
    logger.info("Tool: verify_payment_status %s", order_id)
    return await payment.client.fetch_order(order_id)


async def get_product_catalog_info(product_id: str) -> dict:
    logger.info("Tool: get_product_catalog_info %s", product_id)
    # placeholder: in real app query product DB or service
    return {"product_id": product_id, "title": "Unknown", "return_policy": "7 days"}


def trigger_immediate_voice_call(thread_id: str) -> dict:
    logger.info("Tool: trigger_immediate_voice_call %s", thread_id)
    task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=[thread_id])
    return {"task_id": getattr(task, "id", "")}
