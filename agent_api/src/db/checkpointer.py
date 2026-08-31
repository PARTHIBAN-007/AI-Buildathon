from __future__ import annotations

from loguru import logger

# Placeholder for langgraph checkpointer integration


async def save_agent_state(thread_id: str, state: dict) -> None:
    logger.info("Saving agent state for {}", thread_id)
    return


async def load_agent_state(thread_id: str) -> dict | None:
    logger.info("Loading agent state for {}", thread_id)
    return None
