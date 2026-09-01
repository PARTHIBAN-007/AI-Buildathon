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
    logger.info(f"Tool: send_whatsapp_message to {thread_id}")
    # buttons are provider-specific; convert to template components at call site if needed
    return await whatsapp.send_text_message(to=thread_id, body=text)


async def generate_discounted_payment_link(thread_id: str, amount_in_inr: int, discount_pct: float = 0.0) -> dict:
    logger.info(f"Tool: generate_discounted_payment_link for {thread_id} discount={discount_pct}")
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError("discount_pct must be between 0 and 100")
    discounted_amount = max(1, int(amount_in_inr * (1 - discount_pct / 100.0)))
    return await payment.create_payment_link(amount_in_inr=discounted_amount, description=f"Discounted for {thread_id}")


def schedule_voice_call(thread_id: str, eta_seconds: int = 7200) -> str:
    logger.info(f"Tool: schedule_voice_call for {thread_id} in {eta_seconds}s")
    task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=[thread_id], countdown=eta_seconds)
    return getattr(task, "id", "")


def reschedule_voice_call(celery_task_id: str, new_eta_seconds: int) -> str:
    logger.info(f"Tool: reschedule_voice_call {celery_task_id} to in {new_eta_seconds}s")
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
    logger.info(f"Tool: verify_payment_status {order_id}")
    return await payment.client.fetch_order(order_id)


async def get_product_catalog_info(product_id: str) -> dict:
    logger.info(f"Tool: get_product_catalog_info {product_id}")
    # placeholder: in real app query product DB or service
    return {"product_id": product_id, "title": "Unknown", "return_policy": "7 days"}


def trigger_immediate_voice_call(thread_id: str) -> dict:
    logger.info(f"Tool: trigger_immediate_voice_call {thread_id}")
    task = celery_app.send_task("tasks.trigger_sarvam_voice_call", args=[thread_id])
    return {"task_id": getattr(task, "id", "")}


# --- Summarizer tool ---
async def summarizer(context: dict | None = None, messages: list[dict] | None = None, max_tokens: int = 256) -> str:
    """Summarize provided context and recent messages using the configured LLM client.

    Kept inside tools.py so consumers (LangGraph manager and fallbacks) can reuse it.
    """
    try:
        from src.infrastructure.clients.openai_client import OpenRouterClient  # local import to avoid cycles
        from src.agent.prompts import SYSTEM_PROMPT

        client = OpenRouterClient()
        parts = [
            "Summarize the conversation and context. Provide a concise summary useful for an automated recovery agent. Highlight key facts, customer phone number, outstanding amount, and recommended next action.",
        ]
        if context:
            parts.append(f"Context: {context}")
        if messages:
            parts.append(f"Recent messages: {messages}")
        prompt = "\n\n".join(parts)
        messages_payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await client.chat(messages=messages_payload, max_tokens=max_tokens)
        await client.close()
        return response
    except Exception as exc:
        logger.exception("Summarizer failed: %s", exc)
        return "Unable to summarize automatically. Manual review recommended." 
