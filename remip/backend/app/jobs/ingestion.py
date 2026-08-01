"""Ingestion job orchestration: adapter → area resolution → dedup upsert →
DataIngestionJob bookkeeping. Each registered adapter kind gets its own small
persistence branch below (only OMI exists today); this stays a plain
function so it can run inline (seed bootstrap, tests, Redis-unavailable
fallback) or wrapped as an RQ task (scheduler, worker) identically.
"""
from __future__ import annotations

import logging

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError, BaseAdapter
from app.adapters.omi import OmiAdapter
from app.db.base import SessionLocal, utcnow
from app.models import AdministrativeArea, DataIngestionJob, DataProvider, OmiZoneQuotation

logger = logging.getLogger("remip.ingestion.jobs")

ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {"omi_it": OmiAdapter}


def _resolve_area(db: Session, comune: str, zona_descrizione: str) -> AdministrativeArea | None:
    """Match OMI's raw comune/zona text against our internal geography.
    Real OMI data doesn't carry our UUIDs, so this is the kind of fuzzy
    matching any external open-data source needs — exact name match here,
    good enough for the demo's small fixed dataset."""
    city = db.scalar(
        select(AdministrativeArea).where(
            AdministrativeArea.level == "city",
            AdministrativeArea.name.ilike(comune),
        )
    )
    if city is None:
        return None
    neighborhood = db.scalar(
        select(AdministrativeArea).where(
            AdministrativeArea.level == "neighborhood",
            AdministrativeArea.parent_id == city.id,
            AdministrativeArea.name.ilike(zona_descrizione),
        )
    )
    return neighborhood or city


def _upsert_omi_quotation(db: Session, provider: DataProvider, payload: dict) -> str:
    """Returns 'created' or 'updated'."""
    area = _resolve_area(db, payload["comune"], payload["zona_descrizione"])
    area_id = area.id if area else None
    conditions = [
        OmiZoneQuotation.zone_code == payload["zona_code"],
        OmiZoneQuotation.property_type == payload["tipologia"],
        OmiZoneQuotation.conservation_state == payload["stato"],
        OmiZoneQuotation.period == payload["semestre"],
        OmiZoneQuotation.listing_type == payload["listing_type"],
        (
            OmiZoneQuotation.area_id.is_(None)
            if area_id is None
            else OmiZoneQuotation.area_id == area_id
        ),
    ]
    existing = db.scalar(select(OmiZoneQuotation).where(*conditions))
    if existing:
        existing.price_sqm_min = payload["price_sqm_min"]
        existing.price_sqm_max = payload["price_sqm_max"]
        existing.ingested_at = utcnow()
        return "updated"
    db.add(
        OmiZoneQuotation(
            area_id=area_id,
            provider_id=provider.id,
            comune=payload["comune"],
            zone_code=payload["zona_code"],
            zone_description=payload["zona_descrizione"],
            property_type=payload["tipologia"],
            conservation_state=payload["stato"],
            period=payload["semestre"],
            listing_type=payload["listing_type"],
            price_sqm_min=payload["price_sqm_min"],
            price_sqm_max=payload["price_sqm_max"],
            source_code=provider.code,
        )
    )
    return "created"


def run_ingestion(
    db: Session, provider_code: str, trigger: str = "manual", force: bool = False
) -> DataIngestionJob:
    job = DataIngestionJob(provider_code=provider_code, trigger=trigger, status="running")
    db.add(job)
    db.flush()

    def _fail(message: str) -> DataIngestionJob:
        job.status = "failed"
        job.error_message = message
        job.finished_at = utcnow()
        db.commit()
        logger.warning("ingestion job %s failed: %s", job.id, message)
        return job

    provider = db.scalar(select(DataProvider).where(DataProvider.code == provider_code))
    if provider is None:
        return _fail(f"Unknown provider '{provider_code}'")
    if not provider.enabled and not force:
        return _fail("Provider disabled (kill-switch); pass force=True to override")
    adapter_cls = ADAPTER_REGISTRY.get(provider_code)
    if adapter_cls is None:
        return _fail(f"No adapter registered for '{provider_code}'")

    try:
        raw_records = adapter_cls(enabled=True).run()
    except AdapterError as exc:
        return _fail(str(exc))

    job.records_fetched = len(raw_records)
    created = updated = 0
    if provider_code == "omi_it":
        for raw in raw_records:
            outcome = _upsert_omi_quotation(db, provider, raw.payload)
            created += outcome == "created"
            updated += outcome == "updated"

    provider.last_ingested_at = utcnow()
    job.records_created = created
    job.records_updated = updated
    job.status = "success"
    job.finished_at = utcnow()
    db.commit()
    logger.info(
        "ingestion job %s (%s): %d fetched, %d created, %d updated",
        job.id,
        provider_code,
        job.records_fetched,
        created,
        updated,
    )
    return job


def run_ingestion_job_task(
    provider_code: str, trigger: str = "scheduled", force: bool = False
) -> str:
    """RQ entrypoint: opens its own session (workers don't share one)."""
    with SessionLocal() as db:
        job = run_ingestion(db, provider_code, trigger=trigger, force=force)
        return job.id


def enqueue_or_run_ingestion(
    provider_code: str, trigger: str = "manual", force: bool = False
) -> dict[str, str]:
    """Enqueue via Redis/RQ when reachable; otherwise run inline so ingestion
    still works with zero external services (plain SQLite dev, tests)."""
    try:
        from app.core.queue import get_queue

        queue = get_queue()
        queue.connection.ping()
        rq_job = queue.enqueue(run_ingestion_job_task, provider_code, trigger, force)
        return {"mode": "queued", "rq_job_id": rq_job.id}
    except redis.exceptions.RedisError:
        with SessionLocal() as db:
            job = run_ingestion(db, provider_code, trigger=trigger, force=force)
        return {"mode": "inline", "job_id": job.id, "status": job.status}
