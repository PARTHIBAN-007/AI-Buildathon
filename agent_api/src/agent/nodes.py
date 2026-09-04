from __future__ import annotations

import json
import re
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from loguru import logger

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.state import AgentState
from src.agent.tools import TOOL_DEFINITIONS, summarizer, tool_node
from src.infrastructure.clients.openai_client import OpenRouterClient
from src.infrastructure.postgres.checkpointer import build_checkpoint_saver


def _format_msg_for_llm(msg: Any) -> dict:
    """Converts LangGraph message objects or dicts into strict OpenAI API format."""
    if hasattr(msg, "dict") and callable(msg.dict):
        msg_dict = msg.dict()
    elif isinstance(msg, dict):
        msg_dict = msg
    else:
        msg_dict = {}

    raw_role = msg_dict.get("role") or getattr(msg, "role", None)
    msg_type = msg_dict.get("type") or getattr(msg, "type", None)

    if raw_role in ["user", "assistant", "system", "tool", "developer"]:
        role = raw_role
    elif msg_type in ["human", "user"]:
        role = "user"
    elif msg_type in ["ai", "assistant"]:
        role = "assistant"
    elif msg_type == "tool":
        role = "tool"
    elif msg_type == "system":
        role = "system"
    else:
        role = "user"

    content = msg_dict.get("content")
    if content is None:
        content = getattr(msg, "content", "") or ""

    formatted: Dict[str, Any] = {
        "role": role,
        "content": str(content) if content is not None else "",
    }

    if role == "tool":
        formatted["tool_call_id"] = (
            msg_dict.get("tool_call_id")
            or getattr(msg, "tool_call_id", None)
            or msg_dict.get("id")
            or getattr(msg, "id", "")
        )

    tool_calls = (
        msg_dict.get("tool_calls")
        or getattr(msg, "tool_calls", None)
        or msg_dict.get("additional_kwargs", {}).get("tool_calls")
    )

    if role == "assistant" and tool_calls:
        sanitized_calls = []
        for tc in tool_calls:
            tc_dict = (
                tc.dict()
                if hasattr(tc, "dict") and callable(tc.dict)
                else (tc if isinstance(tc, dict) else {})
            )

            call_id = tc_dict.get("id") or getattr(tc, "id", None)

            # Handle both OpenAI structure (function: {name, arguments})
            # and LangChain structure (name, args)
            func_obj = tc_dict.get("function") or getattr(tc, "function", None)
            if func_obj:
                func_dict = (
                    func_obj.dict()
                    if hasattr(func_obj, "dict") and callable(func_obj.dict)
                    else (func_obj if isinstance(func_obj, dict) else {})
                )
                name = func_dict.get("name") or getattr(func_obj, "name", None)
                args = func_dict.get("arguments") or getattr(func_obj, "arguments", None)
            else:
                name = tc_dict.get("name") or getattr(tc, "name", None)
                args = tc_dict.get("args") or tc_dict.get("arguments") or getattr(tc, "args", None)

            if isinstance(args, dict):
                args_str = json.dumps(args)
            elif isinstance(args, str):
                args_str = args
            else:
                args_str = "{}"

            if call_id and name:
                sanitized_calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args_str,
                    },
                })

        if sanitized_calls:
            formatted["tool_calls"] = sanitized_calls

    return formatted


async def summarizer_node(state: AgentState) -> dict[str, Any]:
    logger.info("Running summarizer node")
    messages = state.get("messages", [])
    context = state.get("context", {})
    summary = await summarizer(context=context, messages=messages)
    return {"summary": summary}


async def chat_node(state: AgentState) -> dict[str, Any]:
    logger.info("Running chat node")
    messages = list(state.get("messages", []))
    context = state.get("context", {})

    formatted_messages = [_format_msg_for_llm(m) for m in messages]

    dynamic_system_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"CURRENT TRANSACTION CONTEXT:\n"
        f"- Active Order ID: {context.get('order_id', 'N/A')}\n"
        f"- Customer Phone: {context.get('customer_phone', 'N/A')}\n"
        f"- Order Amount: ₹{context.get('amount_inr', 0)}\n"
        f"- Failure Reason: {context.get('failure_reason', 'N/A')}\n"
    )

    client = OpenRouterClient()
    payload = [{"role": "system", "content": dynamic_system_prompt}] + formatted_messages

    try:
        response = await client.chat(
            payload,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            return_raw_response=True,
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        assistant_payload: Dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        if tool_calls:
            assistant_payload["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in tool_calls
            ]

        return {"messages": [assistant_payload]}
    finally:
        await client.close()

