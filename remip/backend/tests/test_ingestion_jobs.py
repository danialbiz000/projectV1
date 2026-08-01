import redis
from sqlalchemy import select

from app.db.base import SessionLocal
from app.jobs.ingestion import ADAPTER_REGISTRY, enqueue_or_run_ingestion, run_ingestion
from app.models import DataIngestionJob, DataProvider, OmiZoneQuotation


def test_unknown_provider_fails_cleanly():
    with SessionLocal() as db:
        job = run_ingestion(db, "does-not-exist")
        assert job.status == "failed"
        assert "Unknown provider" in job.error_message


def test_disabled_provider_fails_without_force():
    with SessionLocal() as db:
        job = run_ingestion(db, "portal_generic")  # seeded disabled, ToS-noncompliant
        assert job.status == "failed"
        assert "disabled" in job.error_message.lower()


def test_provider_without_registered_adapter_fails():
    with SessionLocal() as db:
        # demo_it is enabled but intentionally not in the generic job registry
        # (its ingestion happens once, at seed time — see db/seed.py).
        assert "demo_it" not in ADAPTER_REGISTRY
        job = run_ingestion(db, "demo_it")
        assert job.status == "failed"
        assert "no adapter registered" in job.error_message.lower()


def test_force_bypasses_disabled_kill_switch_for_a_registered_adapter():
    with SessionLocal() as db:
        provider = db.scalar(select(DataProvider).where(DataProvider.code == "omi_it"))
        assert provider is not None
        provider.enabled = False
        db.commit()
    try:
        with SessionLocal() as db:
            without_force = run_ingestion(db, "omi_it", force=False)
            assert without_force.status == "failed"
        with SessionLocal() as db:
            with_force = run_ingestion(db, "omi_it", force=True)
            assert with_force.status == "success"
    finally:
        with SessionLocal() as db:
            provider = db.scalar(select(DataProvider).where(DataProvider.code == "omi_it"))
            assert provider is not None
            provider.enabled = True
            db.commit()


def test_rerunning_ingestion_updates_rather_than_duplicates():
    with SessionLocal() as db:
        before_count = db.scalar(
            select(DataProvider.id).where(DataProvider.code == "omi_it")
        )
        assert before_count is not None
        total_before = len(db.scalars(select(OmiZoneQuotation)).all())

        job = run_ingestion(db, "omi_it", trigger="manual", force=True)
        assert job.status == "success"
        assert job.records_created == 0  # already ingested by the seed bootstrap
        assert job.records_updated == job.records_fetched

        total_after = len(db.scalars(select(OmiZoneQuotation)).all())
        assert total_after == total_before  # no duplicate rows created


def test_enqueue_falls_back_to_inline_when_redis_unreachable(monkeypatch):
    """Ingestion must keep working with zero external services (plain
    SQLite/no-Redis dev, and CI where no Redis service is configured)."""

    def broken_get_queue():
        from rq import Queue

        bad_connection = redis.Redis(host="localhost", port=1, socket_connect_timeout=1)
        return Queue("test-queue", connection=bad_connection)

    monkeypatch.setattr("app.core.queue.get_queue", broken_get_queue)
    result = enqueue_or_run_ingestion("omi_it", trigger="manual", force=True)
    assert result["mode"] == "inline"
    assert result["status"] == "success"


def test_ingestion_job_rows_are_persisted():
    with SessionLocal() as db:
        jobs = db.scalars(
            select(DataIngestionJob).where(DataIngestionJob.provider_code == "omi_it")
        ).all()
        assert jobs, "seed bootstrap should have created at least one job row"
        assert any(j.trigger == "seed" for j in jobs)
