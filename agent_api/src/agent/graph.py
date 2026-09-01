from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from src.agent import edges, nodes, tools


class RunnerRegistry:
    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def register(self, thread_id: str, graph: Any, runner: Any) -> None:
        self._store[thread_id] = {"graph": graph, "runner": runner}

    def get(self, thread_id: str) -> Dict[str, Any] | None:
        return self._store.get(thread_id)


_registry = RunnerRegistry()


def _register_tools(graph: Any) -> None:
    registry = {
        "send_whatsapp_message": tools.send_whatsapp_message,
        "generate_discounted_payment_link": tools.generate_discounted_payment_link,
        "schedule_voice_call": tools.schedule_voice_call,
        "reschedule_voice_call": tools.reschedule_voice_call,
        "cancel_recovery_workflow": tools.cancel_recovery_workflow,
        "verify_payment_status": tools.verify_payment_status,
        "get_product_catalog_info": tools.get_product_catalog_info,
        "trigger_immediate_voice_call": tools.trigger_immediate_voice_call,
        "summarizer": tools.summarizer,
    }

    if hasattr(graph, "register_tool"):
        for name, func in registry.items():
            graph.register_tool(name, func)
        return

    if hasattr(graph, "add_tool"):
        for name, func in registry.items():
            graph.add_tool(name, func)
        return

    setattr(graph, "tools", registry)


def _build_graph(thread_id: str, context: Dict[str, Any]) -> Any:
    import langgraph as lg  # type: ignore

    try:
        return lg.Graph(name=f"recovery-{thread_id}", context={"thread_id": thread_id, **context})
    except Exception:
        builder = getattr(lg, "builder", None)
        if builder is None or not hasattr(builder, "GraphBuilder"):
            raise RuntimeError("langgraph Graph API is not available")
        graph_builder = builder.GraphBuilder(name=f"recovery-{thread_id}")
        return graph_builder.build(initial_context={"thread_id": thread_id, **context})


def _wire_graph(graph: Any) -> None:
    graph.add_node(nodes.summarizer_node(name="summarizer"))
    graph.add_node(nodes.outreach_node(name="outreach"))

    for source, target in edges.DEFAULT_EDGES:
        if hasattr(graph, "connect"):
            graph.connect(source, target)
        elif hasattr(graph, "add_edge"):
            graph.add_edge(source, target)
        else:
            graph.__dict__.setdefault("_adj", []).append((source, target))


def start_thread(thread_id: str, context: Dict[str, Any]) -> Any:
    """Create and start the recovery graph."""
    try:
        from langgraph import runtime as lg_runtime  # type: ignore
    except Exception as exc:
        logger.exception("langgraph runtime import failed: %s", exc)
        raise RuntimeError("langgraph package is required for recovery threads")

    graph = _build_graph(thread_id=thread_id, context=context)
    _register_tools(graph)
    _wire_graph(graph)

    runtime = lg_runtime.Runtime()
    if hasattr(runtime, "start"):
        runner = runtime.start(graph)
    elif hasattr(runtime, "run_async"):
        runner = runtime.run_async(graph)
    else:
        runtime.run(graph)
        runner = None

    _registry.register(thread_id=thread_id, graph=graph, runner=runner)
    logger.info("Started LangGraph runner for thread %s", thread_id)
    return runner


def resume_thread(thread_id: str, message: str) -> None:
    entry = _registry.get(thread_id)
    if entry is None:
        raise KeyError(f"No runner for thread {thread_id}")

    runner = entry.get("runner")
    if runner is None:
        graph = entry.get("graph")
        if hasattr(graph, "context"):
            graph.context.setdefault("messages", []).append({"role": "user", "content": message})
            return
        raise RuntimeError("Runner unavailable and graph has no context")

    if hasattr(runner, "send_message"):
        runner.send_message({"role": "user", "content": message})
        return
    if hasattr(runner, "receive"):
        runner.receive({"role": "user", "content": message})
        return
    if hasattr(runner, "post"):
        runner.post({"role": "user", "content": message})
        return

    raise RuntimeError("Runner does not support message delivery")


async def start_agent_thread(thread_id: str, context: Dict[str, Any]) -> None:
    start_thread(thread_id=thread_id, context=context)


async def resume_agent_thread(thread_id: str, message: str, raw: Dict[str, Any] | None = None) -> None:
    resume_thread(thread_id=thread_id, message=message)


async def append_voice_summary(thread_id: str, summary: str | None, raw: Dict[str, Any] | None = None) -> None:
    logger.info("Appending voice summary for thread %s: %s", thread_id, summary)
