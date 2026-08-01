"""Redis-backed job queue (RQ). Ingestion also works without Redis at all —
see jobs/ingestion.py::enqueue_or_run_ingestion — so a plain SQLite dev
environment never depends on this being reachable."""
from __future__ import annotations

import redis
from rq import Queue

from app.core.config import get_settings


def get_redis_connection() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    return Queue(get_settings().ingestion_queue_name, connection=get_redis_connection())
