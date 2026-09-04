from __future__ import annotations

import re
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from loguru import logger

from src.agent import nodes
from src.agent.state import AgentState
from src.agent.tools import tool_node
from src.infrastructure.postgres.checkpointer import build_checkpoint_saver
from src.agent.nodes import chat_node

def sanitize_thread_id(thread_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", str(thread_id))
    return cleaned if cleaned else "default_thread"


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

    initial_prompt = (
        f"SYSTEM ALERT: Payment failed for Order ID '{order_id}'. "
        f"Amount: ₹{amount}. Reason: {reason}. "
        f"Customer Phone: {thread_id}. Initiate recovery workflow."
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

    checkout = None

    # 1. Resolve phone number to the latest active (UNPAID) checkout ID
    if phone_or_thread_id.startswith("+") or phone_or_thread_id.isdigit():
        formatted_phone = f"+{phone_or_thread_id.lstrip('+')}"
        active_checkouts = await list_active_checkouts(formatted_phone)

        if not active_checkouts:
            logger.info(f"No active unpaid checkouts found for phone {formatted_phone}")
            return {"status": "ignored", "reason": "no_active_unpaid_checkout"}

        # Select the most recent unpaid checkout
        checkout = active_checkouts[0]
        target_checkout_id = str(checkout.id)
    else:
        target_checkout_id = phone_or_thread_id
        checkout = await get_checkout(target_checkout_id)

    if not checkout:
        logger.warning(f"No checkout record found for identifier: {phone_or_thread_id}")
        return {"status": "ignored", "reason": "checkout_not_found"}

    # 2. Check payment status for THIS specific checkout
    if checkout.status == "PAID":
        logger.info(f"Checkout {target_checkout_id} is marked PAID; revoking pending recovery jobs")
        voice = VoiceService()
        await voice._cancel_all_pending_jobs_for_checkout(checkout_id=target_checkout_id)
        return {"status": "cancelled", "reason": "payment_already_paid"}

    # 3. Resume LangGraph using checkout_id as thread_id
    safe_thread_id = sanitize_thread_id(target_checkout_id)

    # Deferred import breaks circular dependencies
    from src.agent.builder import build_recovery_graph

    graph = build_recovery_graph()
    payload = {"messages": [{"role": "user", "content": message}]}

    result = await graph.ainvoke(
        payload,
        config={"configurable": {"thread_id": safe_thread_id}},
    )

    logger.info(f"Resumed LangGraph thread '{safe_thread_id}' for checkout_id '{target_checkout_id}'")
    return result


async def append_voice_summary(thread_id: str, summary: str | None, raw: Dict[str, Any] | None = None) -> Dict[str, Any]:
    safe_thread_id = sanitize_thread_id(thread_id)
    graph = build_recovery_graph()
    payload = {
        "messages": [{"role": "assistant", "content": summary or "No voice summary provided"}],
        "summary": summary,
    }
    result = await graph.ainvoke(
        payload,
        config={"configurable": {"thread_id": safe_thread_id}},
    )
    logger.info(f"Appended voice summary for thread {safe_thread_id}")
    return result