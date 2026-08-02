from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbDep
from app.jobs.ingestion import ADAPTER_REGISTRY, enqueue_or_run_ingestion
from app.models import (
    AdministrativeArea,
    AuditLog,
    DataIngestionJob,
    DataProvider,
    ListingVersion,
    Notification,
    PropertyListing,
    User,
)
from app.schemas.listing import SimulateUpdateRequest
from app.services.backup import BackupError, create_backup
from app.services.versioning import apply_listing_update

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def stats(admin: AdminUser, db: DbDep) -> dict:
    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model)) or 0

    return {
        "users": count(User),
        "areas": count(AdministrativeArea),
        "listings": count(PropertyListing),
        "listing_versions": count(ListingVersion),
        "notifications": count(Notification),
        "listings_by_status": {
            row_status: row_count
            for row_status, row_count in db.execute(
                select(PropertyListing.status, func.count()).group_by(PropertyListing.status)
            )
        },
    }


@router.post("/simulate/listing-update")
def simulate_listing_update(body: SimulateUpdateRequest, admin: AdminUser, db: DbDep) -> dict:
    """Demo engine: apply a change as if an external source had sent it.
    Produces a new version, price observation and notifications for watchers."""
    listing = db.get(PropertyListing, body.listing_id)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    try:
        version = apply_listing_update(db, listing, body.changes)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if version is None:
        return {"detail": "No changes detected", "version": None}
    db.add(
        AuditLog(
            user_id=admin.id,
            action="admin.simulate_listing_update",
            entity="listing",
            entity_id=listing.id,
            meta={"diff": version.diff},
        )
    )
    db.commit()
    return {
        "detail": "Update applied",
        "version": {
            "version_number": version.version_number,
            "diff": version.diff,
            "captured_at": version.captured_at.isoformat(),
        },
    }


@router.post("/ingestion/run/{provider_code}")
def trigger_ingestion(provider_code: str, admin: AdminUser, db: DbDep, force: bool = True) -> dict:
    """Run an ingestion job now instead of waiting for the scheduler. Queues
    via Redis/RQ when reachable, otherwise runs inline (see
    jobs/ingestion.py) — always works, even without a worker running."""
    if provider_code not in ADAPTER_REGISTRY:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No adapter registered for '{provider_code}'. Available: {list(ADAPTER_REGISTRY)}",
        )
    db.add(
        AuditLog(
            user_id=admin.id,
            action="admin.trigger_ingestion",
            entity="data_provider",
            entity_id=provider_code,
        )
    )
    db.commit()
    return enqueue_or_run_ingestion(provider_code, trigger="manual", force=force)


@router.get("/ingestion/jobs")
def list_ingestion_jobs(admin: AdminUser, db: DbDep, limit: int = 20) -> list[dict]:
    jobs = db.scalars(
        select(DataIngestionJob).order_by(DataIngestionJob.started_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": j.id,
            "provider_code": j.provider_code,
            "status": j.status,
            "trigger": j.trigger,
            "started_at": j.started_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "records_fetched": j.records_fetched,
            "records_created": j.records_created,
            "records_updated": j.records_updated,
            "error_message": j.error_message,
        }
        for j in jobs
    ]


@router.get("/users")
def list_users(admin: AdminUser, db: DbDep, limit: int = 50, offset: int = 0) -> dict:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    users = db.scalars(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return {
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "onboarding_completed": u.onboarding_completed,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: str, admin: AdminUser, db: DbDep) -> dict:
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot deactivate your own account")
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.is_active = False
    db.add(
        AuditLog(
            user_id=admin.id, action="admin.deactivate_user", entity="user", entity_id=user_id
        )
    )
    db.commit()
    return {"detail": "User deactivated", "user_id": user_id}


@router.post("/users/{user_id}/reactivate")
def reactivate_user(user_id: str, admin: AdminUser, db: DbDep) -> dict:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.is_active = True
    db.add(
        AuditLog(
            user_id=admin.id, action="admin.reactivate_user", entity="user", entity_id=user_id
        )
    )
    db.commit()
    return {"detail": "User reactivated", "user_id": user_id}


@router.post("/sources/{provider_code}/toggle")
def toggle_source(provider_code: str, admin: AdminUser, db: DbDep, enabled: bool) -> dict:
    """Flip a DataProvider's kill-switch. Mirrors the invariant enforced in
    adapters/base.py::BaseAdapter.__init__: a source that isn't ToS-compliant
    can never be enabled, from here or anywhere else."""
    provider = db.scalar(select(DataProvider).where(DataProvider.code == provider_code))
    if provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    if enabled and not provider.tos_compliant:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"'{provider_code}' is not ToS-compliant and cannot be enabled.",
        )
    provider.enabled = enabled
    db.add(
        AuditLog(
            user_id=admin.id,
            action="admin.toggle_source",
            entity="data_provider",
            entity_id=provider_code,
            meta={"enabled": enabled},
        )
    )
    db.commit()
    return {"detail": "Provider updated", "provider_code": provider_code, "enabled": enabled}


@router.post("/backup")
def trigger_backup(admin: AdminUser, db: DbDep) -> dict:
    """On-demand database backup to object storage (M6). See
    services/backup.py — there is deliberately no matching restore
    endpoint; restoring belongs in an operator runbook, not an API call."""
    try:
        result = create_backup()
    except BackupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.add(
        AuditLog(
            user_id=admin.id,
            action="admin.backup",
            entity="database",
            entity_id=result["storage_key"],
            meta=result,
        )
    )
    db.commit()
    return result
