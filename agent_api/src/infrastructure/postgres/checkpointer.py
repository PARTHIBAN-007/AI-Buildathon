from __future__ import annotations

from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from loguru import logger

from src.config import get_settings
from src.infrastructure.postgres.repository import load_agent_state as _load_agent_state
from src.infrastructure.postgres.repository import save_agent_state as _save_agent_state


def build_checkpoint_saver() -> AsyncPostgresSaver:
    return AsyncPostgresSaver.from_conn_string(get_settings().POSTGRES_DSN)


async def save_agent_state(thread_id: str, state: dict[str, Any]) -> None:
    logger.info(f"Saving agent state for {thread_id}")
    await _save_agent_state(thread_id=thread_id, state=state)


async def load_agent_state(thread_id: str) -> dict[str, Any] | None:
    logger.info(f"Loading agent state for {thread_id}")
    return await _load_agent_state(thread_id)
