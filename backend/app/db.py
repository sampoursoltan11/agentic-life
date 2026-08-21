import asyncpg
from pgvector.asyncpg import register_vector

from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Registers the pgvector codec so vector columns round-trip as numpy
    # arrays instead of raw strings.
    await register_vector(conn)


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.database_url, min_size=1, max_size=10, init=_init_connection
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised - call init_pool() at startup")
    return _pool
