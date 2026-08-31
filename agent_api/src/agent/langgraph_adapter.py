from __future__ import annotations

from typing import Any, Dict
from loguru import logger

# This adapter attempts to wire tools and simple graph execution to LangGraph if available.
# If LangGraph is not present or the API differs, it falls back to a lightweight executor
# that sequentially runs the main nodes. Adjust the LangGraph wiring block below to match
# the exact LangGraph API in your environment.

try:
    import langgraph as lg  # type: ignore
    HAS_LANGGRAPH = True
except Exception:
    lg = None
    HAS_LANGGRAPH = False

from src.agent.prompts import SYSTEM_PROMPT
from src.agent import tools
from src.infrastructure.clients.openai_client import OpenRouterClient
from src.config import get_settings

settings = get_settings()


def _register_tools_with_langgraph(graph: Any) -> None:
    """Register application tools with the LangGraph graph instance.

    This function assumes the graph object exposes a register_tool(name, callable) method —
    adapt to your LangGraph API if different.
    """
    try:
        # Example API: graph.register_tool(name, func)
        graph.register_tool("send_whatsapp_message", tools.send_whatsapp_message)
        graph.register_tool("generate_discounted_payment_link", tools.generate_discounted_payment_link)
        graph.register_tool("schedule_voice_call", tools.schedule_voice_call)
        graph.register_tool("reschedule_voice_call", tools.reschedule_voice_call)
        graph.register_tool("cancel_recovery_workflow", tools.cancel_recovery_workflow)
        graph.register_tool("verify_payment_status", tools.verify_payment_status)
        graph.register_tool("get_product_catalog_info", tools.get_product_catalog_info)
        graph.register_tool("trigger_immediate_voice_call", tools.trigger_immediate_voice_call)
        logger.info("Registered tools with LangGraph")
    except Exception as exc:
        logger.warning("Could not register tools with LangGraph: %s", exc)


def build_and_start_langgraph_thread(thread_id: str, context: Dict[str, Any]) -> None:
    """Build and start a LangGraph agent using prebuilt utilities.

    This implementation uses `langgraph.prebuilt.create_react_agent` to assemble an
    agent that can call tools. It binds a minimal set of tools implemented in
    src.agent.tools and starts the agent in a background runtime.

    Notes:
    - The function uses the `openai:` model string that delegates to the OpenAI
      compatible API configured via OPENAI_API_BASE and OPENAI_API_KEY.
    - Checkpointer integration (Postgres) should be added by passing a Checkpointer
      instance to create_react_agent; for now this example uses in-memory store.
    """
    if not HAS_LANGGRAPH:
        raise RuntimeError("LangGraph is not installed")

    try:
        from langgraph.prebuilt import create_react_agent
        # langchain_core tools decorator
        from langchain_core.tools import tool as lc_tool
    except Exception as exc:
        logger.exception("LangGraph prebuilt imports failed: %s", exc)
        raise

    # Create thin wrappers around our existing tool functions and expose them as LangChain tools
    @lc_tool
    async def send_whatsapp_message_tool(thread_id: str, text: str) -> dict:
        return await tools.send_whatsapp_message(thread_id=thread_id, text=text)

    @lc_tool
    async def generate_discounted_payment_link_tool(thread_id: str, amount_in_inr: int, discount_pct: float = 0.0) -> dict:
        return await tools.generate_discounted_payment_link(thread_id=thread_id, amount_in_inr=amount_in_inr, discount_pct=discount_pct)

    @lc_tool
    def schedule_voice_call_tool(thread_id: str, eta_seconds: int = 7200) -> str:
        return tools.schedule_voice_call(thread_id=thread_id, eta_seconds=eta_seconds)

    @lc_tool
    def reschedule_voice_call_tool(celery_task_id: str, new_eta_seconds: int = 3600) -> str:
        return tools.reschedule_voice_call(celery_task_id=celery_task_id, new_eta_seconds=new_eta_seconds)

    @lc_tool
    def cancel_recovery_workflow_tool(celery_task_id: str) -> bool:
        return tools.cancel_recovery_workflow(celery_task_id=celery_task_id)

    @lc_tool
    async def verify_payment_status_tool(order_id: str) -> dict:
        return await tools.verify_payment_status(order_id=order_id)

    @lc_tool
    async def get_product_catalog_info_tool(product_id: str) -> dict:
        return await tools.get_product_catalog_info(product_id=product_id)

    @lc_tool
    def trigger_immediate_voice_call_tool(thread_id: str) -> dict:
        return tools.trigger_immediate_voice_call(thread_id=thread_id)

    tool_list = [
        send_whatsapp_message_tool,
        generate_discounted_payment_link_tool,
        schedule_voice_call_tool,
        reschedule_voice_call_tool,
        cancel_recovery_workflow_tool,
        verify_payment_status_tool,
        get_product_catalog_info_tool,
        trigger_immediate_voice_call_tool,
    ]

    # Create agent graph using a model string that relies on OpenAI-compatible API
    model_string = f"openai:{getattr(settings, 'OPENAI_MODEL', 'google/gemma-4-31b-it:free')}"

    try:
        # Use create_react_agent to produce a compiled state graph
        compiled = create_react_agent(
            model=model_string,
            tools=tool_list,
            prompt=SYSTEM_PROMPT,
            # For production integrate a Checkpointer here (e.g., Postgres-based)
            checkpointer=None,
            name=f"recovery-agent-{thread_id}",
        )

        # Start the runtime for the compiled graph. Use langgraph.runtime.Runtime
        from langgraph.runtime import Runtime
        runtime = Runtime()
        initial_state = {"messages": [], "context": context}
        # run returns when finished; for background processing you'd use Runtime.run_async or start a background runner
        runtime.run(compiled, initial_state)
        logger.info("LangGraph agent started for thread %s", thread_id)
    except Exception as exc:
        logger.exception("Failed to build/start LangGraph agent: %s", exc)
        raise


async def _fallback_sequential_runner(thread_id: str, context: Dict[str, Any]) -> None:
    """Fallback lightweight runner: compose via LLM, then run tools sequentially.

    This keeps behavior consistent without requiring LangGraph.
    """
    logger.info("Using fallback sequential runner for thread %s", thread_id)
    try:
        client = OpenRouterClient()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context: {context}"},
        ]
        composed = await client.chat(messages=messages, max_tokens=256)
        await client.close()
    except Exception as exc:
        logger.warning("LLM compose failed in fallback runner: %s", exc)
        composed = f"Hello — we noticed a payment issue for ₹{context.get('total_amount')}. Reply for a payment link."

    # send WhatsApp outreach
    try:
        await tools.send_whatsapp_message(thread_id=thread_id, text=composed)
    except Exception:
        logger.exception("Failed to send WhatsApp outreach in fallback runner")

    # schedule voice call
    try:
        task_id = tools.schedule_voice_call(thread_id=thread_id, eta_seconds=7200)
        logger.info("Fallback runner scheduled voice call task=%s", task_id)
    except Exception:
        logger.exception("Failed to schedule voice call in fallback runner")


def start_thread(thread_id: str, context: Dict[str, Any]):
    """Public entry to start an agent recovery thread. Uses LangGraph when available,
    otherwise uses a fallback sequential runner (async behavior handled by caller).
    """
    if HAS_LANGGRAPH:
        try:
            build_and_start_langgraph_thread(thread_id, context)
            return
        except Exception:
            logger.exception("LangGraph start failed; falling back to sequential runner")

    # Fallback: caller should await this coroutine
    return _fallback_sequential_runner(thread_id, context)


def resume_thread(thread_id: str, message: str, raw: Dict[str, Any] | None = None):
    """Resume a running thread. If LangGraph is available, route the message into the graph's runner.
    Otherwise, call the agent.graph.resume_agent_thread fallback.
    """
    if HAS_LANGGRAPH:
        try:
            # PSEUDO: find runner and deliver message
            runner = lg.get_runner_for_thread(thread_id)
            runner.send_message({"role": "user", "content": message})
            return
        except Exception:
            logger.exception("LangGraph resume failed; falling back to simple resume")

    # Fallback to existing simple resume
    from src.agent.graph import resume_agent_thread as _resume

    return _resume(thread_id=thread_id, message=message, raw=raw)
