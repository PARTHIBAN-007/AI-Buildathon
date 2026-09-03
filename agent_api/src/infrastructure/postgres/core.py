from __future__ import annotations

from typing import Any, AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
import anyio

from src.config import get_settings
from src.infrastructure.postgres.models import Base

settings = get_settings()

# Use synchronous SQLAlchemy engine/session per template to avoid async_sessionmaker issues
engine: Engine = create_engine(
    str(settings.POSTGRES_DSN),
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@asynccontextmanager
async def async_session_factory() -> AsyncGenerator[Session, None]:
    """Async context manager that yields a sync SQLAlchemy Session by running
    session creation/close on a worker thread. This keeps the public API async
    while using sync SQLAlchemy internals as requested.
    """
    def _create_session():
        return SessionLocal()

    session: Session = await anyio.to_thread.run_sync(_create_session)
    try:
        yield session
    finally:
        def _close():
            try:
                session.close()
            except Exception:
                pass
        await anyio.to_thread.run_sync(_close)


@asynccontextmanager
async def get_db() -> AsyncGenerator[Session, None]:
    """FastAPI dependency yielding request-scoped DB sessions (sync under the hood)."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    # Create tables using synchronous engine
    def _create_all():
        Base.metadata.create_all(bind=engine)

    await anyio.to_thread.run_sync(_create_all)


# Checkpoint saver lifecycle for LangGraph AsyncPostgresSaver
_checkpoint_stack: AsyncExitStack | None = None
_checkpoint_saver: Any | None = None


async def init_checkpoint_saver() -> None:
    """Initialize and hold the AsyncPostgresSaver instance for the app lifetime.

    Enter the async context returned by AsyncPostgresSaver.from_conn_string at
    startup and keep the saver instance for use by StateGraph.compile.
    """
    global _checkpoint_stack, _checkpoint_saver
    if _checkpoint_saver is not None:
        return
    _checkpoint_stack = AsyncExitStack()
    saver_cm = AsyncPostgresSaver.from_conn_string(str(settings.POSTGRES_DSN))
    _checkpoint_saver = await _checkpoint_stack.enter_async_context(saver_cm)


async def close_checkpoint_saver() -> None:
    global _checkpoint_stack, _checkpoint_saver
    if _checkpoint_stack is not None:
        await _checkpoint_stack.aclose()
        _checkpoint_stack = None
        _checkpoint_saver = None


def get_checkpoint_saver() -> Any | None:
    return _checkpoint_saver


async def close_db() -> None:
    # dispose is sync; run in thread
    def _dispose():
        engine.dispose()

    await anyio.to_thread.run_sync(_dispose)
