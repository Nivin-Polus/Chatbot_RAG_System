from datetime import datetime, timedelta
from typing import Callable

from fastapi import Depends, HTTPException, Request, status

from app.config import settings

try:
    import redis  # type: ignore
except ImportError:
    redis = None


def _get_redis_client():
    """Return a Redis client if configured and available, otherwise None."""
    if not settings.USE_REDIS or redis is None:
        return None

    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        socket_timeout=settings.REDIS_TIMEOUT,
    )


def rate_limiter(
    limit: int = 60,
    window_seconds: int = 60,
) -> Callable:
    """
    Simple per-identity rate limiter.

    Uses Redis when available; otherwise, it becomes a no-op (never blocks).
    Identity is based on authenticated user_id when present, or client IP as a fallback.
    """

    redis_client = _get_redis_client()

    async def dependency(request: Request):
        # If Redis is not available, skip rate limiting (fail-open rather than break the app)
        if redis_client is None:
            return

        # Determine identity: prefer authenticated user, then IP address
        identity = None
        user = getattr(request.state, "current_user", None)
        if user and getattr(user, "user_id", None):
            identity = f"user:{user.user_id}"
        else:
            client_host = request.client.host if request.client else "unknown"
            identity = f"ip:{client_host}"

        window_start = int(datetime.utcnow().timestamp() // window_seconds * window_seconds)
        key = f"rate:{identity}:{window_start}"

        try:
            # Increment counter with TTL at first use
            current = redis_client.incr(key)
            if current == 1:
                # First hit in this window; set TTL to window size
                redis_client.expire(key, window_seconds)

            if current > limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please slow down and try again shortly.",
                )
        except HTTPException:
            raise
        except Exception:
            # On Redis error, fail-open (do not block request)
            return

    return dependency


