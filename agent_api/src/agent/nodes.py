from __future__ import annotations

from typing import Any
from loguru import logger

# Node builders are intentionally minimal and return descriptors that match common
# LangGraph node APIs. They avoid wrapping each tiny tool — tools are referenced
# by name and registered on the graph.


def summarizer_node(graph: Any, name: str = "summarizer") -> dict:
    """Descriptor for a summarizer node. The graph implementation will use the
    registered 'summarizer' tool to produce a concise state summary.
    """
    logger.debug("Constructing summarizer node %s", name)
    return {"id": name, "type": "tool", "tool": "summarizer", "outputs": ["summary"]}


def outreach_node(graph: Any, name: str = "outreach") -> dict:
    """Descriptor for an outreach node that sends WhatsApp messages and may
    call other tools (e.g., generate_discounted_payment_link).
    """
    logger.debug("Constructing outreach node %s", name)
    return {"id": name, "type": "composed", "steps": [
        {"action": "send_whatsapp_message", "args": ["thread_id", "message_text"]},
    ], "outputs": ["sent"]}
