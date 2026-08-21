"""Fixed-window rate limiting backed by Redis (architecture.md provisions
Redis for "cache/jobs" - this is Phase 12's first real use of it; nothing
in this stack touched Redis before).
"""

import logging
from functools import lru_cache

import redis

from app.core.config import get_settings

logger = logging.getLogger("app.rate_limit")


@lru_cache
def get_redis_client() -> redis.Redis:
    # protocol=2: this project's local dev Redis (tools/start-redis-windows.ps1)
    # is the portable Redis 5.x-for-Windows build (no admin rights needed,
    # since Docker Desktop doesn't start in this environment - see README's
    # Prerequisites) - it predates RESP3/HELLO (Redis 6.0+), and redis-py's
    # default protocol negotiation sends HELLO unconditionally otherwise,
    # which a real 5.x server rejects with "unknown command 'HELLO'".
    #
    # Public (V3): promoted from a private helper so app/services/coach_service.py
    # can reuse this exact client/connection handling for its Redis value-cache
    # instead of duplicating it - this module's second real use case for Redis,
    # after rate limiting.
    return redis.Redis.from_url(
        get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1, protocol=2
    )


def check_rate_limit(
    key: str, *, limit: int, window_seconds: int, client: redis.Redis | None = None
) -> bool:
    """Returns True if this call is within the limit (and counts it).
    Fixed-window counter: INCR the key, set its TTL on first use each
    window. Fails OPEN - if Redis is unreachable, the request is allowed
    and a warning is logged - rate limiting is defense-in-depth, not a
    feature worth taking the app down over."""
    redis_client = client if client is not None else get_redis_client()
    try:
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, window_seconds)
        return current <= limit
    except redis.RedisError:
        logger.warning("rate_limit_backend_unavailable key=%s", key)
        return True


def check_redis_connectivity() -> bool:
    """Honest reachability check for /health (Phase 14) - deliberately NOT
    fail-open like check_rate_limit above. A health endpoint that always
    reports "ok" regardless of the real backend state defeats the point of
    a deployment platform routing traffic based on it."""
    try:
        return bool(get_redis_client().ping())
    except redis.RedisError:
        return False
