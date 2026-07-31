from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbDep
from app.models import (
    AdministrativeArea,
    AuditLog,
    ListingVersion,
    Notification,
    PropertyListing,
    User,
)
from app.schemas.listing import SimulateUpdateRequest
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
