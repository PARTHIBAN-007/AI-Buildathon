from __future__ import annotations

from loguru import logger

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
except Exception:
    create_async_engine = None
    AsyncSession = None
    sessionmaker = None

from src.config import get_settings

settings = get_settings()


def async_session_factory():
    if create_async_engine is None:
        raise RuntimeError("SQLAlchemy async dependencies not installed")

    engine = create_async_engine(settings.POSTGRES_DSN, echo=False)
    return sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)()
