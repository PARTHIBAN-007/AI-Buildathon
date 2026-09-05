from __future__ import annotations

import json
from typing import Any, Dict, Optional
from uuid import UUID

from loguru import logger
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from src.agent.prompts import SYSTEM_PROMPT
from src.application.whatsapp_service import WhatsAppService
from src.application.payment_service import PaymentService
from src.application.voice_service import VoiceService
from src.infrastructure.clients.openai_client import OpenRouterClient
from src.application.recovery_service import cancel_checkout_recovery
from src.infrastructure.postgres.repository import get_checkout, get_checkout_by_razorpay_order_id, update_checkout_payment_link

whatsapp = WhatsAppService()
payment = PaymentService()








def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Safely extracts an attribute or dict key from a checkout model or object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


async def _resolve_checkout_entity(
    checkout_id_or_ref: Optional[str],
    config: Optional[RunnableConfig] = None,
) -> Any | None:
    """Resolves DB checkout entity from UUID, Razorpay Order ID, or RunnableConfig context."""
    target_id = None
    if checkout_id_or_ref and str(checkout_id_or_ref).strip() and str(checkout_id_or_ref).strip().lower() != "none":
        target_id = str(checkout_id_or_ref).strip()

    if not target_id and config and isinstance(config, dict):
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id") or configurable.get("checkout_id")
        if thread_id and str(thread_id) != "default_thread":
            target_id = str(thread_id)

    if not target_id:
        return None

    try:
        checkout = await get_checkout(target_id)
        if not checkout and target_id.startswith("order_"):
            checkout = await get_checkout_by_razorpay_order_id(target_id)
        return checkout
    except Exception as e:
        logger.warning(f"Failed to resolve checkout by ID/ref '{target_id}': {e}")
        return None


def _sanitize_phone(phone_number: Optional[str], fallback_phone: Optional[str]) -> str:
    """Ensures phone_number isn't a UUID or order string passed by mistake."""
    if not phone_number:
        return fallback_phone or ""

    val = str(phone_number).strip()
    if val.startswith("order_"):
        return fallback_phone or ""

    try:
        UUID(val)
        return fallback_phone or ""
    except ValueError:
        return val


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
async def generate_payment_link(
    phone_number: str,
    amount_in_inr: float,
    checkout_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> str:
    """Generates a standard, full-price payment retry link."""
    try:
        checkout = await _resolve_checkout_entity(checkout_id, config)

        real_db_checkout_id = str(_get_val(checkout, "id")) if checkout else None
        db_phone = _get_val(checkout, "customer_phone") if checkout else None
        valid_phone = _sanitize_phone(phone_number, fallback_phone=db_phone)

        result = await payment.create_payment_link(
            amount_in_inr=int(amount_in_inr),
            description=f"Payment recovery for {valid_phone or 'customer'}",
            checkout_id=real_db_checkout_id,
            customer={"contact": valid_phone} if valid_phone else None,
        )

        if isinstance(result, dict):
            plink_id = result.get("id")
            short_url = result.get("short_url") or result.get("payment_link") or ""

            if real_db_checkout_id and plink_id:
                await update_checkout_payment_link(
                    checkout_id=real_db_checkout_id,
                    payment_link_id=str(plink_id),
                )

            return short_url or str(result)

        return str(result)
    except Exception as e:
        logger.error(f"Generate payment link tool error: {e}")
        return f"Error generating payment link: {e}"


@tool
async def generate_discounted_payment_link(
    phone_number: str,
    amount_in_inr: float,
    discount_pct: float = 0.0,
    checkout_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """Generate a discounted Razorpay payment link for the customer phone number."""
    try:
        checkout = await _resolve_checkout_entity(checkout_id, config)

        real_db_checkout_id = str(_get_val(checkout, "id")) if checkout else None
        db_phone = _get_val(checkout, "customer_phone") if checkout else None
        valid_phone = _sanitize_phone(phone_number, fallback_phone=db_phone)

        discount_pct = max(0.0, min(100.0, float(discount_pct)))
        discounted_amount = max(1.0, float(amount_in_inr) * (1.0 - discount_pct / 100.0))

        logger.info(f"Tool: generate_discounted_payment_link for {valid_phone} discount={discount_pct}%")

        result = await payment.create_payment_link(
            amount_in_inr=int(discounted_amount),
            description=f"Discounted recovery payment for {valid_phone or 'customer'}",
            checkout_id=real_db_checkout_id,
            customer={"contact": valid_phone} if valid_phone else None,
        )

        payment_url = ""
        if isinstance(result, dict):
            plink_id = result.get("id")
            payment_url = result.get("short_url") or result.get("payment_link") or ""

            if real_db_checkout_id and plink_id:
                await update_checkout_payment_link(
                    checkout_id=real_db_checkout_id,
                    payment_link_id=str(plink_id),
                    discount_pct=discount_pct,
                )

        return {
            "success": True,
            "payment_link": payment_url or str(result),
            "discounted_amount": discounted_amount,
            "checkout_id": real_db_checkout_id,
        }
    except Exception as e:
        logger.error(f"Discounted payment link tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def reschedule_voice_call(
    new_eta_seconds: int,
    checkout_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    item_name: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """Reschedule an existing scheduled voice call strictly for a target checkout_id."""
    try:
        checkout = await _resolve_checkout_entity(checkout_id, config)
        if not checkout:
            return {"success": False, "error": "Missing checkout_id context for rescheduling call."}

        target_checkout_id = str(_get_val(checkout, "id"))
        phone = _get_val(checkout, "customer_phone")
        logger.info(f"Tool: reschedule_voice_call checkout={target_checkout_id} to {new_eta_seconds}s")

        service = VoiceService()
        result = await service.reschedule_call(
            checkout_id=target_checkout_id,
            new_eta_seconds=int(new_eta_seconds),
            phone=phone,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Reschedule call tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def cancel_recovery_workflow(
    checkout_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """Cancel all active recovery tasks and scheduled voice calls strictly for a given checkout_id."""
    try:
        checkout = await _resolve_checkout_entity(checkout_id, config)
        if not checkout:
            return {"success": False, "error": "Missing checkout_id context for cancellation."}

        db_checkout_id = str(_get_val(checkout, "id"))
        logger.info(f"Tool: cancel_recovery_workflow checkout_id={db_checkout_id}")

        await cancel_checkout_recovery(checkout_id=db_checkout_id)
        return {"status": "cancelled", "success": True, "checkout_id": db_checkout_id}
    except Exception as e:
        logger.error(f"Cancel recovery tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def verify_payment_status(
    checkout_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """Verify payment status strictly for a given checkout_id in PostgreSQL."""
    try:
        checkout = await _resolve_checkout_entity(checkout_id, config)
        if not checkout:
            return {"success": False, "error": "Checkout record not found in database."}

        raw_amount = _get_val(checkout, "total_amount")
        amount_val = float(raw_amount) if raw_amount is not None else 0.0

        return {
            "success": True,
            "checkout_id": str(_get_val(checkout, "id")),
            "status": _get_val(checkout, "status"),
            "amount_inr": amount_val,
            "phone": _get_val(checkout, "customer_phone"),
            "order_id": _get_val(checkout, "razorpay_order_id"),
        }
    except Exception as e:
        logger.error(f"Verify payment tool error: {e}")
        return {"success": False, "error": str(e)}


@tool
async def trigger_immediate_voice_call(
    phone_number: str,
    checkout_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    amount_in_inr: Optional[float] = None,
    item_name: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """Trigger an immediate outbound voice call strictly for a checkout_id."""
    try:
        checkout = await _resolve_checkout_entity(checkout_id, config)
        db_checkout_id = str(_get_val(checkout, "id")) if checkout else checkout_id

        logger.info(f"Tool: trigger_immediate_voice_call phone={phone_number}, checkout_id={db_checkout_id}")

        metadata: Dict[str, Any] = {}
        if customer_name:
            metadata["customer_name"] = customer_name
        if item_name:
            metadata["item_name"] = item_name

        if amount_in_inr is not None:
            metadata["amount_in_inr"] = float(amount_in_inr)
        elif checkout and _get_val(checkout, "total_amount") is not None:
            metadata["amount_in_inr"] = float(_get_val(checkout, "total_amount"))

        service = VoiceService()
        result = await service.trigger_immediate_call(
            phone=phone_number,
            checkout_id=db_checkout_id,
            metadata=metadata,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Trigger call tool error: {e}")
        return {"success": False, "error": str(e)}

async def summarizer(context: dict | None = None, messages: list | None = None, max_tokens: int = 256) -> str:
    client = OpenRouterClient()
    try:
        parts = [
            "Summarize the conversation and context. Highlight key facts, customer phone number, outstanding amount, and recommended next action."
        ]
        if context:
            parts.append(f"Context: {context}")
        if messages:
            clean_msgs = [
                m if isinstance(m, dict) else {"role": getattr(m, "type", "user"), "content": str(getattr(m, "content", ""))}
                for m in messages
            ]
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
            "parameters": tool_fn.args_schema.model_json_schema()
            if hasattr(tool_fn.args_schema, "model_json_schema")
            else tool_fn.args_schema.schema(),
        },
    }
    for tool_fn in tools
]


async def tool_node(state: dict, config: Optional[RunnableConfig] = None):
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
                output = await tool_fn.ainvoke(args, config=config)
            else:
                output = tool_fn.invoke(args, config=config)
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