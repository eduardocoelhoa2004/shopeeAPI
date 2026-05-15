from __future__ import annotations

import asyncio
import ssl
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from src.core.config.settings import settings
from src.infrastructure.database.base import Base
from src.modules.shopee.models import ShopeeOffer  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database.sqlalchemy_url)

target_metadata = Base.metadata


def _build_ssl_context() -> ssl.SSLContext | bool:
    mode = settings.database.ssl_mode
    if mode == "disable":
        return False
    if mode == "require":
        context_ssl = ssl.create_default_context()
        context_ssl.check_hostname = False
        context_ssl.verify_mode = ssl.CERT_NONE
        return context_ssl
    return ssl.create_default_context()


def _build_connect_args() -> dict[str, object]:
    return {
        "timeout": settings.database.connect_timeout,
        "ssl": _build_ssl_context(),
    }


def run_migrations_offline() -> None:
    url = settings.database.sqlalchemy_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(
        settings.database.sqlalchemy_url,
        poolclass=pool.NullPool,
        connect_args=_build_connect_args(),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
