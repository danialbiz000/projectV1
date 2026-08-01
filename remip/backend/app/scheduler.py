"""Periodic ingestion scheduler: `python -m app.scheduler`.

Runs as its own process (see docker-compose.yml `scheduler` service),
re-reading enabled providers on every tick so enabling/disabling a source
(the adapter kill-switch) takes effect without a restart.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.jobs.ingestion import ADAPTER_REGISTRY, enqueue_or_run_ingestion
from app.models import DataProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("remip.scheduler")


def tick() -> None:
    with SessionLocal() as db:
        providers = db.scalars(select(DataProvider).where(DataProvider.enabled.is_(True))).all()
    for provider in providers:
        if provider.code not in ADAPTER_REGISTRY:
            continue
        logger.info("scheduling ingestion for provider %s", provider.code)
        result = enqueue_or_run_ingestion(provider.code, trigger="scheduled")
        logger.info("provider %s: %s", provider.code, result)


if __name__ == "__main__":
    settings = get_settings()
    scheduler = BlockingScheduler()
    scheduler.add_job(tick, "interval", minutes=settings.ingestion_interval_minutes)
    logger.info(
        "ingestion scheduler started: every %d minutes", settings.ingestion_interval_minutes
    )
    tick()  # run once immediately so a fresh stack has data without waiting
    scheduler.start()
