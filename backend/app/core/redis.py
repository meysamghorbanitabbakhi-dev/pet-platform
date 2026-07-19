from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def ping_redis() -> None:
    # redis-py's async Redis.ping() is typed `Awaitable[bool] | bool` because
    # the command is defined once and shared with the sync client -- it is
    # always awaitable here, this is an upstream stub imprecision.
    await get_redis().ping()  # type: ignore[misc]


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
