"""RQ worker entrypoint: `python -m app.worker`.

Runs as its own container/process (see docker-compose.yml `worker` service)
so ingestion never blocks API request handling.
"""
from __future__ import annotations

import logging

from rq import Worker

from app.core.config import get_settings
from app.core.queue import get_redis_connection

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    settings = get_settings()
    worker = Worker([settings.ingestion_queue_name], connection=get_redis_connection())
    worker.work()
