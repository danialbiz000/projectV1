"""Listing versioning: every change produces an immutable ListingVersion with a
field-level diff, a PriceObservation when the price moved, and notification
events for watching users."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import ListingVersion, PriceObservation, PropertyListing
from app.services.notifications import notify_listing_event
from app.services.storage import save_snapshot

TRACKED_FIELDS = (
    "price",
    "title",
    "description",
    "photos_count",
    "size_sqm",
    "rooms",
    "energy_class",
    "status",
)


def _listing_snapshot(listing: PropertyListing) -> dict[str, Any]:
    return {
        "price": listing.current_price,
        "title": listing.title,
        "description": listing.description,
        "photos_count": listing.photos_count,
        "size_sqm": listing.property.size_sqm if listing.property else None,
        "rooms": listing.property.rooms if listing.property else None,
        "energy_class": listing.property.energy_class if listing.property else None,
        "status": listing.status,
    }


def _store_snapshot(listing_id: str, version_number: int, snapshot: dict[str, Any]) -> str:
    key = f"listings/{listing_id}/v{version_number}.json"
    body = json.dumps(
        {"listing_id": listing_id, "version_number": version_number, **snapshot}, default=str
    ).encode()
    return save_snapshot(key, body)


def create_initial_version(db: Session, listing: PropertyListing) -> ListingVersion:
    snap = _listing_snapshot(listing)
    version = ListingVersion(
        listing_id=listing.id,
        version_number=1,
        captured_at=listing.first_seen_at,
        diff={},
        snapshot_key=_store_snapshot(listing.id, 1, snap),
        **snap,
    )
    db.add(version)
    db.add(
        PriceObservation(
            listing_id=listing.id,
            observed_at=listing.first_seen_at,
            price=listing.current_price,
            currency=listing.currency,
        )
    )
    return version


def classify_event(diff: dict[str, dict[str, Any]]) -> str:
    """Map a diff to the most relevant notification event type."""
    if "status" in diff:
        new_status = diff["status"]["new"]
        if new_status == "removed":
            return "listing_removed"
        if new_status == "relisted":
            return "listing_relisted"
        if new_status == "sold":
            return "possible_sale"
        return "status_change"
    if "price" in diff:
        old, new = diff["price"]["old"], diff["price"]["new"]
        return "price_drop" if new < old else "price_increase"
    if "photos_count" in diff:
        return "photos_change"
    return "listing_update"


def apply_listing_update(
    db: Session, listing: PropertyListing, changes: dict[str, Any]
) -> ListingVersion | None:
    """Apply changes to a listing, producing a new version.

    Returns the new version, or None when the changes are a no-op.
    """
    before = _listing_snapshot(listing)
    diff: dict[str, dict[str, Any]] = {}
    for field, new_value in changes.items():
        if field not in TRACKED_FIELDS:
            raise ValueError(f"Field '{field}' is not versionable")
        if before.get(field) != new_value:
            diff[field] = {"old": before.get(field), "new": new_value}
    if not diff:
        return None

    now = utcnow()
    if "price" in diff:
        listing.current_price = float(diff["price"]["new"])
        db.add(
            PriceObservation(
                listing_id=listing.id,
                observed_at=now,
                price=listing.current_price,
                currency=listing.currency,
            )
        )
    if "title" in diff:
        listing.title = diff["title"]["new"]
    if "description" in diff:
        listing.description = diff["description"]["new"]
    if "photos_count" in diff:
        listing.photos_count = int(diff["photos_count"]["new"])
    if "status" in diff:
        listing.status = diff["status"]["new"]
    if listing.property is not None:
        if "size_sqm" in diff:
            listing.property.size_sqm = float(diff["size_sqm"]["new"])
        if "rooms" in diff:
            listing.property.rooms = int(diff["rooms"]["new"])
        if "energy_class" in diff:
            listing.property.energy_class = diff["energy_class"]["new"]
    listing.last_seen_at = now

    last_number = db.scalar(
        select(ListingVersion.version_number)
        .where(ListingVersion.listing_id == listing.id)
        .order_by(ListingVersion.version_number.desc())
        .limit(1)
    )
    version_number = (last_number or 0) + 1
    new_snapshot = _listing_snapshot(listing)
    version = ListingVersion(
        listing_id=listing.id,
        version_number=version_number,
        captured_at=now,
        diff=diff,
        snapshot_key=_store_snapshot(listing.id, version_number, new_snapshot),
        **new_snapshot,
    )
    db.add(version)
    db.flush()

    notify_listing_event(db, listing, classify_event(diff), diff, version.version_number)
    return version
