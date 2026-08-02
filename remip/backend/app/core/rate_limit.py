"""Distributed rate limiting for auth endpoints (M6).

Redis-backed fixed-window counter keyed by (bucket, client IP, minute).
Same reachability pattern as jobs/ingestion.py's queue fallback: when Redis
isn't reachable, an in-process in-memory counter takes over so the endpoint
still degrades gracefully instead of failing open or hard-erroring — it just
only limits a single backend process rather than a whole fleet until Redis
is available.
"""
from __future__ import annotations

import time

import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_memory_counters: dict[str, int] = {}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _window_key(bucket: str, identifier: str) -> str:
    window = int(time.time() // 60)
    return f"ratelimit:{bucket}:{identifier}:{window}"


def _increment_memory(key: str) -> int:
    # The window is baked into `key`, so stale entries just stop being
    # written to; cap growth with a cheap full reset rather than tracking
    # per-key expiry — acceptable for a single-process dev fallback.
    if len(_memory_counters) > 5000:
        _memory_counters.clear()
    _memory_counters[key] = _memory_counters.get(key, 0) + 1
    return _memory_counters[key]


def _increment(key: str) -> int:
    try:
        conn = redis.from_url(
            get_settings().redis_url, socket_connect_timeout=0.2, socket_timeout=0.2
        )
        pipe = conn.pipeline()
        pipe.incr(key)
        pipe.expire(key, 120)
        count, _ = pipe.execute()
        return int(count)
    except redis.exceptions.RedisError:
        return _increment_memory(key)


def enforce_rate_limit(bucket: str, request: Request, limit_per_minute: int) -> None:
    """Raises 429 once more than ``limit_per_minute`` requests land in the
    same bucket from the same client within the current minute window."""
    key = _window_key(bucket, _client_ip(request))
    if _increment(key) > limit_per_minute:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Troppe richieste. Riprova tra meno di un minuto.",
            headers={"Retry-After": "60"},
        )
