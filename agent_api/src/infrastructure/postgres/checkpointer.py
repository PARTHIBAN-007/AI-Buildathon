from __future__ import annotations

from typing import Any
from loguru import logger

from src.infrastructure.postgres.core import get_checkpoint_saver
from src.infrastructure.postgres.repository import load_agent_state as _load_agent_state
from src.infrastructure.postgres.repository import save_agent_state as _save_agent_state


def build_checkpoint_saver() -> Any | None:
    saver = get_checkpoint_saver()
    if saver is None:
        logger.warning(
            "No checkpoint saver available; StateGraph will compile without persistence. "
            "Ensure init_checkpoint_saver() was awaited during app startup."
        )
    return saver


async def save_agent_state(thread_id: str, state: dict[str, Any]) -> None:
    logger.info(f"Saving agent state for {thread_id}")
    try:
        await _save_agent_state(thread_id=thread_id, state=state)
    except Exception as e:
        logger.error(f"Failed to save agent state for {thread_id}: {e}")


async def load_agent_state(thread_id: str) -> dict[str, Any] | None:
    logger.info(f"Loading agent state for {thread_id}")
    try:
        return await _load_agent_state(thread_id)
    except Exception as e:
        logger.error(f"Failed to load agent state for {thread_id}: {e}")
        return None