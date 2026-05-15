from __future__ import annotations

from typing import Final

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from src.core.config.settings import settings


class RedisClientManager:
    def __init__(self) -> None:
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None

    def _create_pool(self) -> ConnectionPool:
        return ConnectionPool.from_url(
            settings.redis.url,
            max_connections=settings.redis.max_connections,
            socket_timeout=settings.redis.socket_timeout,
            socket_connect_timeout=settings.redis.socket_connect_timeout,
            health_check_interval=settings.redis.health_check_interval,
        )

    def get_client(self) -> Redis:
        if self._client is None:
            if self._pool is None:
                self._pool = self._create_pool()
            self._client = Redis(connection_pool=self._pool)
        return self._client

    async def ping(self) -> bool:
        client = self.get_client()
        return bool(await client.ping())

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._pool is not None:
            await self._pool.disconnect(inuse_connections=True)
            self._pool = None


redis_manager: Final[RedisClientManager] = RedisClientManager()


def get_redis_client() -> Redis:
    return redis_manager.get_client()


async def ping_redis() -> bool:
    return await redis_manager.ping()


async def close_redis() -> None:
    await redis_manager.close()
