from __future__ import annotations

import re
from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from loguru import logger

from src.agent import nodes
from src.agent.nodes import chat_node
from src.agent.state import AgentState
from src.agent.tools import tool_node
from src.infrastructure.postgres.checkpointer import build_checkpoint_saver
from langchain.messages import HumanMessage


def sanitize_thread_id(thread_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", str(thread_id))
    return cleaned if cleaned else "default_thread"


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Safely extracts a field from either an ORM object or a dictionary."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _route_after_chat(state: Dict[str, Any]) -> str:
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1]
    if isinstance(last_message, dict):
        tool_calls = last_message.get("tool_calls")
    else:
        tool_calls = getattr(last_message, "tool_calls", None)

    return "tools" if tool_calls else END


def build_recovery_graph() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("chat", chat_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "chat")
    graph.add_conditional_edges(
        "chat",
        _route_after_chat,
        {
            "tools": "tools",
            END: END,
        },
    )
    graph.add_edge("tools", "chat")
    return graph.compile(checkpointer=build_checkpoint_saver())


async def start_agent_thread(thread_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    safe_thread_id = sanitize_thread_id(thread_id)
    graph = build_recovery_graph()

    order_id = context.get("order_id", "UNKNOWN")
    amount = context.get("amount_inr", 0)
    reason = context.get("failure_reason", "Payment failed")
    customer_name = context.get("customer_name") or "Customer"

    initial_prompt = (
        f"Hi {customer_name}! I'm Arjun from VectorTech, your Razorpay payment support agent. "
        f"A follow-up call is scheduled for your recent purchase, and you can also chat with me here to discuss the payment. "
        f"If you want, you can connect on the scheduled call or reschedule it anytime. "
        f"SYSTEM ALERT: Payment failed for Order ID '{order_id}'. Amount: ₹{amount}. "
        f"Reason: {reason}. Customer Phone: {thread_id}. Initiate recovery workflow."
    )

    payload = {
        "messages": [{"role": "user", "content": initial_prompt}],
        "context": context,
        "customer_profile": context.get("customer_profile", {}),
        "checkout_id": context.get("checkout_id") or order_id,
        "summary": None,
    }

    result = await graph.ainvoke(
        payload,
        config={"configurable": {"thread_id": safe_thread_id}},
    )
    logger.info(f"Started LangGraph thread {safe_thread_id} for Order {order_id}")
    return result



async def resume_agent_thread(
    phone_or_thread_id: str,
    message: str,
    raw: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Resolves phone/checkout_id, validates payment status, and resumes the active LangGraph thread."""
    from src.application.voice_service import VoiceService
    from src.infrastructure.postgres.repository import get_checkout, list_active_checkouts
    from src.application.whatsapp_service import WhatsAppService

    whatsapp_service = WhatsAppService()
    checkout = None

    # 1. Resolve phone number or thread_id to an active checkout
    if phone_or_thread_id.startswith("+") or phone_or_thread_id.isdigit():
        formatted_phone = f"+{phone_or_thread_id.lstrip('+')}"
        active_checkouts = await list_active_checkouts(formatted_phone)

        if not active_checkouts:
            logger.info(f"No active unpaid checkouts found for phone {formatted_phone}")
            await whatsapp_service.send_text_message(
                to=formatted_phone,
                body="We couldn't find any active unpaid orders for your account.",
            )
            return {"status": "ignored", "reason": "no_active_unpaid_checkout"}

        checkout = active_checkouts[0]
    else:
        checkout = await get_checkout(phone_or_thread_id)

    if not checkout:
        logger.warning(f"No checkout record found for identifier: {phone_or_thread_id}")
        return {"status": "ignored", "reason": "checkout_not_found"}

    # Extract fields safely across both dict and ORM object models
    checkout_id = str(_get_field(checkout, "id", phone_or_thread_id))
    checkout_status = _get_field(checkout, "status")

    # 2. Check payment status for THIS specific checkout
    if checkout_status == "PAID":
        logger.info(f"Checkout {checkout_id} is marked PAID; revoking pending recovery jobs")
        voice = VoiceService()
        cancel_fn = getattr(
            voice,
            "_cancel_pending_jobs",
            getattr(voice, "_cancel_all_pending_jobs_for_checkout", None),
        )
        if cancel_fn:
            await cancel_fn(checkout_id=checkout_id)
        return {"status": "cancelled", "reason": "payment_already_paid"}

    # 3. Resume LangGraph using checkout_id as thread_id
    safe_thread_id = sanitize_thread_id(checkout_id)
    graph = build_recovery_graph()
    payload = {"messages": [{"role": "user", "content": message}]}

    result = await graph.ainvoke(
        payload,
        config={"configurable": {"thread_id": safe_thread_id}},
    )

    logger.info(f"Resumed LangGraph thread '{safe_thread_id}' for checkout_id '{checkout_id}'")
    return result


async def append_voice_summary(
    thread_id: str,
    status: str,
    phone: str,
    summary: str | None = None,
    raw: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    safe_thread_id = sanitize_thread_id(thread_id)
    graph = build_recovery_graph()

    # Construct an imperative prompt based on call status
    if status in ["busy", "no-answer", "rejected", "failed"]:
        event_content = (
            f"[SYSTEM EVENT: VOICE_CALL_FAILED]\n"
            f"Voice call attempt to {phone} for checkout_id '{safe_thread_id}' failed with status '{status}'.\n\n"
            f"REQUIRED ACTIONS:\n"
            f"1. Execute `send_whatsapp_message` to notify the customer that we tried calling them, provide the payment link, and offer help on WhatsApp.\n"
            f"2. Execute `reschedule_voice_call` to queue a retry call in 1800 seconds (30 minutes)."
        )
    else:
        event_content = (
            f"[SYSTEM EVENT: VOICE_CALL_COMPLETED]\n"
            f"Voice call to {phone} for checkout_id '{safe_thread_id}' completed with status '{status}'.\n"
            f"Call Details / Transcript: {summary or 'No transcript provided.'}"
        )

    # CRITICAL: Injected as HumanMessage/User role so the LLM actively responds with tool execution
    payload = {
        "messages": [HumanMessage(content=event_content)],
        "summary": summary,
    }

    result = await graph.ainvoke(
        payload,
        config={"configurable": {"thread_id": safe_thread_id}},
    )
    logger.info(f"Appended voice summary for thread {safe_thread_id}")
    return result