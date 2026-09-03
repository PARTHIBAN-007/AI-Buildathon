from __future__ import annotations

from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from loguru import logger

from src.infrastructure.postgres.core import get_checkpoint_saver
from src.infrastructure.postgres.repository import load_agent_state as _load_agent_state
from src.infrastructure.postgres.repository import save_agent_state as _save_agent_state


def build_checkpoint_saver():
    """Return the live saver instance created at app startup, or None.

    The actual AsyncPostgresSaver is created and entered in
    infrastructure.postgres.core.init_checkpoint_saver() during FastAPI
    startup. Here we return the in-memory saver instance so StateGraph.compile
    receives a valid saver object rather than an async context manager.
    """
    saver = get_checkpoint_saver()
    if saver is None:
        logger.debug("No checkpoint saver available; StateGraph will compile without a checkpointer.")
    return saver


async def save_agent_state(thread_id: str, state: dict[str, Any]) -> None:
    logger.info(f"Saving agent state for {thread_id}")
    await _save_agent_state(thread_id=thread_id, state=state)


async def load_agent_state(thread_id: str) -> dict[str, Any] | None:
    logger.info(f"Loading agent state for {thread_id}")
    return await _load_agent_state(thread_id)
