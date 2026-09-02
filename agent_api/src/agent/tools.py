from __future__ import annotations

from loguru import logger

from src.agent.prompts import SYSTEM_PROMPT
from src.application.whatsapp_service import WhatsAppService
from src.application.payment_service import PaymentService
from src.application.voice_service import VoiceService
from src.infrastructure.clients.openai_client import OpenRouterClient


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



async def reschedule_voice_call(job_id: str, new_eta_seconds: int) -> dict:
    logger.info(f"Tool: reschedule_voice_call job={job_id} to in {new_eta_seconds}s")
    return await voice.reschedule_call(job_id=job_id, new_eta_seconds=new_eta_seconds)


async def cancel_recovery_workflow(job_id: str) -> bool:
    logger.info(f"Tool: cancel_recovery_workflow {job_id}")
    return await voice.cancel_call(job_id=job_id)


async def verify_payment_status(order_id: str) -> dict:
    logger.info(f"Tool: verify_payment_status {order_id}")
    return await payment.client.fetch_order(order_id)


async def trigger_immediate_voice_call(thread_id: str, checkout_id: str | None = None) -> dict:
    logger.info(f"Tool: trigger_immediate_voice_call {thread_id}")
    return await voice.trigger_immediate_call(phone=thread_id, checkout_id=checkout_id)


# --- Summarizer tool ---
async def summarizer(context: dict | None = None, messages: list[dict] | None = None, max_tokens: int = 256) -> str:
    """Summarize provided context and recent messages using the configured LLM client.

    Kept inside tools.py so consumers (LangGraph manager and fallbacks) can reuse it.
    """
    try:
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
        logger.exception(f"Summarizer failed: {exc}")
        return "Unable to summarize automatically. Manual review recommended."
