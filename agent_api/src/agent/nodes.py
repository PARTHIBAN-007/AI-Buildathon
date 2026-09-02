from __future__ import annotations

from typing import Any

from loguru import logger

from src.agent.state import AgentState
from src.agent.tools import summarizer
from src.infrastructure.clients.openai_client import OpenRouterClient
from src.agent.prompts import SYSTEM_PROMPT


async def summarizer_node(state: AgentState) -> dict[str, Any]:
    logger.info("Running summarizer node")
    messages = state.get("messages", [])
    context = state.get("context", {})
    summary = await summarizer(context=context, messages=messages)
    return {"summary": summary}


async def chat_node(state: AgentState) -> dict[str, Any]:
    """Primary chat node: run the LLM and allow tool actions directly in this node.

    Summarization is still triggered only when the conversation grows beyond a
    rough token threshold, but the graph itself does not route through a separate
    outreach node.
    """
    logger.info("Running chat node")
    messages = list(state.get("messages", []))
    context = state.get("context", {})

    total_chars = sum(len(m.get("content", "")) for m in messages)
    token_estimate = total_chars // 4
    TOKEN_THRESHOLD = 1500

    if token_estimate > TOKEN_THRESHOLD:
        logger.info(f"Token estimate {token_estimate} exceeds threshold {TOKEN_THRESHOLD}; summarizing")
        summary = await summarizer(context=context, messages=messages)
        messages = [{"role": "system", "content": f"Summary: {summary}"}]
        state["summary"] = summary

    client = OpenRouterClient()
    payload = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    try:
        response = await client.chat(payload)
    finally:
        await client.close()

    return {"messages": [*messages, {"role": "assistant", "content": response}]}
