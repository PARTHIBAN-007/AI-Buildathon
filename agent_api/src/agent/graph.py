from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from loguru import logger

from src.agent import nodes
from src.agent.state import AgentState
from src.infrastructure.postgres.checkpointer import build_checkpoint_saver


def build_recovery_graph() -> Any:
    """Create the recovery graph with chat as the primary node.

    The agent decides and executes tool calls directly from chat. Summarization is
    only triggered as an internal helper when history grows too large; there is no
    separate outreach node in the graph.
    """
    graph = StateGraph(AgentState)
    graph.add_node("chat", nodes.chat_node)
    graph.add_edge(START, "chat")
    graph.add_edge("chat", END)
    return graph.compile(checkpointer=build_checkpoint_saver())


async def start_agent_thread(thread_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Create and invoke a recovery flow for a new thread using a Postgres-backed checkpoint."""
    graph = build_recovery_graph()
    payload = {
        "messages": [{"role": "user", "content": context.get("failure_reason") or "start recovery"}],
        "context": context,
        "customer_profile": context.get("customer_profile", {}),
        "checkout_id": context.get("checkout_id"),
        "summary": None,
    }

    result = await graph.ainvoke(
        payload,
        # config={"configurable": {"thread_id": thread_id}},
    )
    logger.info(f"Started LangGraph thread {thread_id}")
    return result


async def resume_agent_thread(thread_id: str, message: str, raw: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Resume a thread using the Postgres-backed checkpoint.

    This function also guards recovery by checking whether the checkout is already
    paid. If the checkout is paid, pending Celery jobs are revoked and the flow
    returns early.
    """
    from src.application.voice_service import VoiceService
    from src.infrastructure.postgres.repository import list_checkouts_by_phone, update_checkout_status

    phone = thread_id
    checkouts = await list_checkouts_by_phone(phone)
    if any(item.status == "PAID" for item in checkouts):
        logger.info(f"Payment already marked as PAID for {phone}; revoking pending Celery jobs before continuing")
        voice = VoiceService()
        await voice._cancel_all_pending_jobs_for_checkout(phone=phone)
        return {"status": "cancelled", "reason": "payment_already_paid"}

    if "paid" in message.lower() or "payment done" in message.lower() or "i have paid" in message.lower():
        for checkout in checkouts:
            if checkout.status != "PAID":
                await update_checkout_status(checkout.id, status="PAID")
        voice = VoiceService()
        await voice._cancel_all_pending_jobs_for_checkout(phone=phone)
        logger.info(f"Customer confirmed payment for {phone}; cancelling active recovery jobs")
        return {"status": "paid", "reason": "payment_confirmed"}

    graph = build_recovery_graph()
    payload = {"messages": [{"role": "user", "content": message}]}
    result = await graph.ainvoke(
        payload,
        config={"configurable": {"thread_id": thread_id}},
    )
    logger.info(f"Resumed LangGraph thread {thread_id}")
    return result


async def append_voice_summary(thread_id: str, summary: str | None, raw: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Append a voice summary into the thread state using the Postgres-backed checkpoint."""
    graph = build_recovery_graph()
    payload = {
        "messages": [{"role": "assistant", "content": summary or "No voice summary provided"}],
        "summary": summary,
    }
    result = await graph.ainvoke(
        payload,
        config={"configurable": {"thread_id": thread_id}},
    )
    logger.info(f"Appended voice summary for thread {thread_id}")
    return result
