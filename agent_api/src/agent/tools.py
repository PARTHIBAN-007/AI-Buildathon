from __future__ import annotations

import json
import re
from typing import Any, Optional

from loguru import logger
from langchain_core.tools import tool

from src.agent.prompts import SYSTEM_PROMPT
from src.application.whatsapp_service import WhatsAppService
from src.application.payment_service import PaymentService
from src.application.voice_service import VoiceService
from src.infrastructure.clients.openai_client import OpenRouterClient
from src.application.recovery_service import cancel_checkout_recovery
from src.infrastructure.postgres.repository import get_checkout, list_scheduled_jobs_for_checkout

whatsapp = WhatsAppService()
payment = PaymentService()
voice = VoiceService()


@tool
async def send_whatsapp_message(phone_number: str, text: str) -> dict:
    """Send a WhatsApp text message to the customer phone number."""
    try:
        logger.info(f"Tool: send_whatsapp_message to {phone_number}")
        return await whatsapp.send_text_message(to=phone_number, body=text)
    except Exception as e:
        logger.error(f"WhatsApp tool error: {e}")
        return {"success": False, "error": str(e)}

@tool
async def generate_payment_link(phone_number: str, amount_in_inr: int) -> str:
    """Generates a standard, full-price payment retry link."""
    # Added async/await here
    return await payment.create_payment_link(
        amount_in_inr=amount_in_inr, 
        description=f"Payment recovery for {phone_number}"
    )


@tool
async def generate_discounted_payment_link(phone_number: str, amount_in_inr: float, discount_pct: float = 0.0) -> dict:
    """Generate a discounted Razorpay payment link for the customer phone number."""
    try:
        logger.info(f"Tool: generate_discounted_payment_link for {phone_number} discount={discount_pct}")
        discount_pct = max(0.0, min(100.0, float(discount_pct)))
        discounted_amount = max(1.0, float(amount_in_inr) * (1.0 - discount_pct / 100.0))
        return await payment.create_payment_link(
            amount_in_inr=int(discounted_amount),
            description=f"Discounted recovery payment for {phone_number}"
        )
    except Exception as e:
        logger.error(f"Payment link tool error: {e}")
        return {"success": False, "error": str(e)}

@tool
async def schedule_voice_call(checkout_id: str, phone_number: str, eta_seconds: int = 3600) -> dict:
    """Schedule an automated voice recovery call for a checkout_id after eta_seconds delay."""
    try:
        logger.info(f"Tool: schedule_voice_call for checkout={checkout_id}, phone={phone_number} in {eta_seconds}s")
        service = VoiceService()
        result = await service.schedule_call(
            phone=phone_number,
            eta_seconds=int(eta_seconds),
            checkout_id=checkout_id,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Schedule call tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def reschedule_voice_call(checkout_id: str, new_eta_seconds: int) -> dict:
    """Reschedule an existing scheduled voice call for a checkout_id to a new ETA in seconds."""
    try:
        logger.info(f"Tool: reschedule_voice_call checkout={checkout_id} to {new_eta_seconds}s")
        jobs = await list_scheduled_jobs_for_checkout(checkout_id=checkout_id)
        active_jobs = [j for j in jobs if j.status in {"SCHEDULED", "PENDING"}]

        if not active_jobs:
            return {"success": False, "error": f"No active scheduled call found for checkout_id={checkout_id}"}

        service = VoiceService()
        result = await service.reschedule_call(job_id=active_jobs[0].id, new_eta_seconds=int(new_eta_seconds))
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Reschedule call tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def cancel_recovery_workflow(checkout_id: str) -> dict:
    """Cancel all active recovery tasks and scheduled voice calls for a given checkout_id."""
    try:
        logger.info(f"Tool: cancel_recovery_workflow checkout_id={checkout_id}")
        await cancel_checkout_recovery(checkout_id=checkout_id)
        return {"status": "cancelled", "success": True, "checkout_id": checkout_id}
    except Exception as e:
        logger.error(f"Cancel recovery tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def verify_payment_status(checkout_id: str) -> dict:
    """Verify payment status for a given checkout_id in PostgreSQL source of truth."""
    try:
        logger.info(f"Tool: verify_payment_status checkout_id={checkout_id}")
        checkout = await get_checkout(checkout_id)
        if not checkout:
            return {"success": False, "error": f"Checkout ID '{checkout_id}' not found in database."}

        return {
            "success": True,
            "checkout_id": checkout.id,
            "status": checkout.status,
            "amount_inr": checkout.total_amount,
            "phone": checkout.customer_phone,
            "order_id": checkout.razorpay_order_id,
        }
    except Exception as e:
        logger.error(f"Verify payment tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def trigger_immediate_voice_call(phone_number: str, checkout_id: Optional[str] = None) -> dict:
    """Trigger an immediate outbound voice call to the customer phone number."""
    try:
        logger.info(f"Tool: trigger_immediate_voice_call phone={phone_number}, checkout_id={checkout_id}")
        service = VoiceService()
        result = await service.trigger_immediate_call(phone=phone_number, checkout_id=checkout_id)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Trigger call tool error: {e}")
        return {"success": False, "error": str(e)}


# @tool
# async def get_product_catalog_info(product_id: str) -> dict:
#     """Return lightweight product catalog record for the given product identifier."""
#     return {"product_id": product_id, "title": "Checkout Item", "return_policy": "7 days"}


async def summarizer(context: dict | None = None, messages: list | None = None, max_tokens: int = 256) -> str:
    client = OpenRouterClient()
    try:
        parts = [
            "Summarize the conversation and context. Highlight key facts, customer phone number, outstanding amount, and recommended next action."
        ]
        if context:
            parts.append(f"Context: {context}")
        if messages:
            clean_msgs = [m if isinstance(m, dict) else {"role": getattr(m, "type", "user"), "content": str(getattr(m, "content", ""))} for m in messages]
            parts.append(f"Recent messages: {clean_msgs}")
        
        prompt = "\n\n".join(parts)
        payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        return await client.chat(messages=payload, max_tokens=max_tokens)
    except Exception as exc:
        logger.error(f"Summarizer failed: {exc}")
        return "Unable to summarize automatically."
    finally:
        await client.close()


tools = [
    schedule_voice_call,
    reschedule_voice_call,
    cancel_recovery_workflow,
    verify_payment_status,
    trigger_immediate_voice_call,
    send_whatsapp_message,
    generate_payment_link,
    generate_discounted_payment_link,
]

tools_by_name = {tool_fn.name: tool_fn for tool_fn in tools}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": tool_fn.name,
            "description": tool_fn.description,
            "parameters": tool_fn.args_schema.model_json_schema() if hasattr(tool_fn.args_schema, "model_json_schema") else tool_fn.args_schema.schema(),
        },
    }
    for tool_fn in tools
]


async def tool_node(state: dict):
    results = []
    messages = state.get("messages", [])
    if not messages:
        return {"messages": results}

    last_message = messages[-1]
    if isinstance(last_message, dict):
        tool_calls = last_message.get("tool_calls", [])
    else:
        tool_calls = getattr(last_message, "tool_calls", []) or []

    for call in tool_calls:
        if isinstance(call, dict):
            call_name = call.get("function", {}).get("name") or call.get("name")
            call_id = call.get("id")
            arguments = call.get("function", {}).get("arguments") or call.get("args") or "{}"
        else:
            call_name = getattr(call, "name", None) or getattr(getattr(call, "function", None), "name", None)
            call_id = getattr(call, "id", None)
            arguments = getattr(getattr(call, "function", None), "arguments", "{}") or getattr(call, "args", "{}")

        if not call_name:
            continue

        tool_fn = tools_by_name.get(call_name)
        if tool_fn is None:
            results.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": call_name,
                "content": json.dumps({"error": f"Tool '{call_name}' is not registered"}),
            })
            continue

        if isinstance(arguments, str):
            try:
                args = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                args = {}
        else:
            args = arguments or {}

        try:
            if hasattr(tool_fn, "ainvoke"):
                output = await tool_fn.ainvoke(args)
            else:
                output = tool_fn.invoke(args)
        except Exception as err:
            logger.error(f"Execution error in tool '{call_name}': {err}")
            output = {"error": f"Execution failed: {str(err)}"}

        results.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": call_name,
            "content": json.dumps(output, default=str),
        })

    return {"messages": results}