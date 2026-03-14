"""Redis connection management.

Provides a connection pool and helper functions for the job queue,
rate limiting, and caching subsystems.
"""

import logging
from functools import lru_cache

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool | None:
    global _pool
    if _pool is not None:
        return _pool
    url = settings.REDIS_URL
    if not url:
        return None
    _pool = redis.ConnectionPool.from_url(url, decode_responses=True)
    return _pool


def get_redis() -> redis.Redis | None:
    """Get a Redis client from the connection pool.

    Returns None if REDIS_URL is not configured (graceful degradation).
    """
    pool = _get_pool()
    if pool is None:
        return None
    try:
        client = redis.Redis(connection_pool=pool)
        client.ping()
        return client
    except (redis.ConnectionError, redis.TimeoutError) as exc:
        logger.warning("Redis unavailable: %s", exc)
        return None


def redis_available() -> bool:
    """Quick check if Redis is reachable."""
    client = get_redis()
    if client is None:
        return False
    try:
        return client.ping()
    except Exception:
        return False
