from __future__ import annotations

import ssl
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config.settings import settings


def _build_ssl_context() -> ssl.SSLContext | bool:
    mode = settings.database.ssl_mode
    if mode == "disable":
        return False
    if mode == "require":
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    return ssl.create_default_context()


def _build_connect_args() -> dict[str, object]:
    return {
        "timeout": settings.database.connect_timeout,
        "ssl": _build_ssl_context(),
    }


engine: AsyncEngine = create_async_engine(
    settings.database.sqlalchemy_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,
    connect_args=_build_connect_args(),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
