from __future__ import annotations

from loguru import logger
from typing import Dict, Any, List

from src.agent.prompts import SYSTEM_PROMPT
from src.agent import tools
from src.agent.langgraph_adapter import start_thread, resume_thread

# Use OpenRouter client if available
try:
    from src.infrastructure.clients.openai_client import OpenRouterClient
except Exception:
    OpenRouterClient = None


async def _compose_initial_message(system_prompt: str, context: Dict[str, Any]) -> str:
    """Deprecated in favour of LangGraph adapter: kept for backward compatibility.

    If LangGraph adapter is available, the adapter will handle LLM composition. This
    function remains as a local fallback for older callers.
    """
    """Compose a personalized outreach message using the configured LLM.

    Falls back to a simple templated message when the LLM client is not available.
    """
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context: {context}"},
    ]

    if OpenRouterClient is None:
        logger.warning("OpenRouterClient not available — using fallback template message")
        total = context.get("total_amount")
        return f"Hi! We noticed a problem with your payment for ₹{total}. Reply if you'd like a secure payment link to complete your purchase."

    client = OpenRouterClient()
    try:
        text = await client.chat(messages=messages, max_tokens=256)
        await client.close()
        return text
    except Exception as exc:
        logger.exception("LLM composition failed: %s", exc)
        return f"Hi! We noticed a problem with your payment for ₹{context.get('total_amount')}. Reply for help."


async def start_agent_thread(thread_id: str, context: Dict[str, Any]) -> None:
    """Start agent thread via LangGraph adapter when possible; otherwise use local fallback.

    The langgraph_adapter.start_thread may return a coroutine (fallback) or start a
    background runner for LangGraph. Handle both cases.
    """
    logger.info("Starting agent thread (adapter) for %s", thread_id)
    result = start_thread(thread_id=thread_id, context=context)
    # If adapter returned a coroutine (fallback sequential runner), await it
    if hasattr(result, "__await__"):
        await result
    # Otherwise assume the adapter started background execution
    return


async def resume_agent_thread(thread_id: str, message: str, raw: Dict[str, Any] | None = None) -> None:
    """Resume an existing agent thread via LangGraph adapter when possible.

    If LangGraph adapter isn't available or fails, fallback to local resume logic.
    """
    logger.info("Resuming agent thread (adapter) %s with message=%s", thread_id, message)
    result = resume_thread(thread_id=thread_id, message=message, raw=raw)
    if hasattr(result, "__await__"):
        await result
    return


async def append_voice_summary(thread_id: str, summary: str | None, raw: Dict[str, Any] | None = None) -> None:
    logger.info("Appending voice summary to thread %s: %s", thread_id, summary)
    # Persist summary into checkpointer or DB and notify agent — placeholder
    return
