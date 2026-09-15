from collections.abc import AsyncGenerator
from typing import Optional
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: Optional[ConnectionPool] = None


async def init_redis_pool() -> ConnectionPool:
    """Inicializa o pool de conexões assíncronas do Redis."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def close_redis_pool() -> None:
    """Fecha o pool de conexões do Redis de forma graciosa."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


async def get_redis_client() -> Redis:
    """Obtém uma instância do cliente Redis compartilhando o pool de conexões."""
    pool = await init_redis_pool()
    return Redis(connection_pool=pool)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Dependency para injeção do cliente Redis em endpoints e services."""
    client = await get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
