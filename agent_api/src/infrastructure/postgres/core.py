from __future__ import annotations

import re
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, AsyncGenerator

import anyio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.infrastructure.postgres.models import Base

settings = get_settings()


def _sanitize_dsn(dsn_str: str) -> str:
    """Normalize 'localhost' to '127.0.0.1' to prevent IPv6 (::1) connection refusal issues."""
    return dsn_str.replace("@localhost:", "@127.0.0.1:").replace("@localhost/", "@127.0.0.1/")


def _get_saver_dsn(dsn_str: str) -> str:
    """Strip SQLAlchemy driver suffixes (e.g. +psycopg2) for AsyncPostgresSaver / psycopg3."""
    clean_dsn = _sanitize_dsn(dsn_str)
    return re.sub(r"^postgresql\+[a-zA-Z0-9_]+://", "postgresql://", clean_dsn)


db_url = _sanitize_dsn(str(settings.POSTGRES_DSN))
saver_url = _get_saver_dsn(str(settings.POSTGRES_DSN))

engine: Engine = create_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@asynccontextmanager
async def async_session_factory() -> AsyncGenerator[Session, None]:
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
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    def _create_all():
        Base.metadata.create_all(bind=engine)

    try:
        await anyio.to_thread.run_sync(_create_all)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")


_checkpoint_stack: AsyncExitStack | None = None
_checkpoint_saver: Any | None = None


async def init_checkpoint_saver() -> None:
    """Initialize AsyncPostgresSaver at app startup with explicit table migration setup."""
    global _checkpoint_stack, _checkpoint_saver
    if _checkpoint_saver is not None:
        return

    _checkpoint_stack = AsyncExitStack()
    try:
        saver_cm = AsyncPostgresSaver.from_conn_string(saver_url)
        _checkpoint_saver = await _checkpoint_stack.enter_async_context(saver_cm)
        await _checkpoint_saver.setup()
        logger.info("Postgres checkpoint saver initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize checkpoint saver on {saver_url}: {e}")
        if _checkpoint_stack:
            await _checkpoint_stack.aclose()
            _checkpoint_stack = None
        _checkpoint_saver = None


async def close_checkpoint_saver() -> None:
    global _checkpoint_stack, _checkpoint_saver
    if _checkpoint_stack is not None:
        await _checkpoint_stack.aclose()
        _checkpoint_stack = None
        _checkpoint_saver = None


def get_checkpoint_saver() -> Any | None:
    return _checkpoint_saver


async def close_db() -> None:
    def _dispose():
        engine.dispose()

    await anyio.to_thread.run_sync(_dispose)