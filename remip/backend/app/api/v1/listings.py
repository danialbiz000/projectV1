from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DbDep
from app.models import (
    AdministrativeArea,
    ListingVersion,
    MarketMetric,
    PhysicalProperty,
    PriceObservation,
    PropertyListing,
)
from app.schemas.listing import ListingDetail, ListingSummary, PricePoint, VersionOut
from app.services.comparables import estimate_value, find_comparables
from app.services.storage import get_snapshot

router = APIRouter(prefix="/listings", tags=["listings"])

SORTABLE = {
    "price": PropertyListing.current_price,
    "published_at": PropertyListing.published_at,
    "size_sqm": PhysicalProperty.size_sqm,
}


def descendant_area_ids(db: Session, area_id: str) -> list[str]:
    """The area itself plus all nested children (city → neighborhoods, etc.)."""
    ids, frontier = [area_id], [area_id]
    while frontier:
        children = db.scalars(
            select(AdministrativeArea.id).where(AdministrativeArea.parent_id.in_(frontier))
        ).all()
        frontier = list(children)
        ids.extend(frontier)
    return ids


def _days_on_market(listing: PropertyListing) -> int:
    published = listing.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return max((datetime.now(UTC) - published).days, 0)


def _version_out(v: ListingVersion) -> VersionOut:
    return VersionOut(
        version_number=v.version_number,
        captured_at=v.captured_at,
        price=v.price,
        status=v.status,
        diff=v.diff,
        has_snapshot=bool(v.snapshot_key),
    )


def _summary(listing: PropertyListing, area_name: str) -> ListingSummary:
    prop = listing.property
    return ListingSummary(
        id=listing.id,
        title=listing.title,
        listing_type=listing.listing_type,
        status=listing.status,
        current_price=listing.current_price,
        currency=listing.currency,
        price_per_sqm=round(listing.current_price / prop.size_sqm, 0) if prop.size_sqm else None,
        size_sqm=prop.size_sqm,
        rooms=prop.rooms,
        property_type=prop.property_type,
        energy_class=prop.energy_class,
        area_id=prop.area_id,
        area_name=area_name,
        lat=prop.lat,
        lon=prop.lon,
        published_at=listing.published_at,
        days_on_market=_days_on_market(listing),
        photos_count=listing.photos_count,
        is_demo_data=listing.provider.is_demo,
    )


@router.get("")
def search_listings(
    db: DbDep,
    area_id: str | None = None,
    listing_type: str = Query(default="sale", pattern="^(sale|rent)$"),
    listing_status: str = Query(default="active", alias="status"),
    property_type: str | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_size: float | None = Query(default=None, ge=0),
    max_size: float | None = Query(default=None, ge=0),
    min_rooms: int | None = Query(default=None, ge=0),
    energy_class: str | None = None,
    sort_by: str = Query(default="published_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    if sort_by not in SORTABLE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"sort_by must be one of {list(SORTABLE)}")
    query = (
        select(PropertyListing, AdministrativeArea.name)
        .join(PhysicalProperty, PropertyListing.property_id == PhysicalProperty.id)
        .join(AdministrativeArea, PhysicalProperty.area_id == AdministrativeArea.id)
        .where(PropertyListing.listing_type == listing_type)
    )
    if listing_status != "all":
        query = query.where(PropertyListing.status == listing_status)
    if area_id:
        query = query.where(PhysicalProperty.area_id.in_(descendant_area_ids(db, area_id)))
    if property_type:
        query = query.where(PhysicalProperty.property_type == property_type)
    if min_price is not None:
        query = query.where(PropertyListing.current_price >= min_price)
    if max_price is not None:
        query = query.where(PropertyListing.current_price <= max_price)
    if min_size is not None:
        query = query.where(PhysicalProperty.size_sqm >= min_size)
    if max_size is not None:
        query = query.where(PhysicalProperty.size_sqm <= max_size)
    if min_rooms is not None:
        query = query.where(PhysicalProperty.rooms >= min_rooms)
    if energy_class:
        query = query.where(PhysicalProperty.energy_class == energy_class)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = SORTABLE[sort_by]
    query = query.order_by(column.desc() if sort_dir == "desc" else column.asc())
    rows = db.execute(query.limit(limit).offset(offset)).all()
    return {
        "items": [_summary(listing, area_name) for listing, area_name in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{listing_id}", response_model=ListingDetail)
def get_listing(listing_id: str, db: DbDep) -> ListingDetail:
    listing = db.get(PropertyListing, listing_id)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    prop = listing.property
    area = db.get(AdministrativeArea, prop.area_id)
    observations = db.scalars(
        select(PriceObservation)
        .where(PriceObservation.listing_id == listing.id)
        .order_by(PriceObservation.observed_at)
    ).all()
    comparables = find_comparables(db, listing)
    estimate = estimate_value(comparables, prop.size_sqm)

    deviation = None
    latest_metric = db.scalars(
        select(MarketMetric)
        .where(MarketMetric.area_id == prop.area_id, MarketMetric.listing_type == "sale")
        .order_by(MarketMetric.period.desc())
        .limit(1)
    ).first()
    if listing.listing_type == "sale" and latest_metric and prop.size_sqm:
        listing_sqm = listing.current_price / prop.size_sqm
        deviation = round(
            (listing_sqm - latest_metric.avg_price_sqm) / latest_metric.avg_price_sqm * 100, 1
        )

    other_listings = db.scalars(
        select(PropertyListing).where(
            PropertyListing.property_id == listing.property_id,
            PropertyListing.id != listing.id,
        )
    ).all()
    duplicate_listings = [
        {
            "listing_id": other.id,
            "agency_name": other.agency.name if other.agency else None,
            "price": other.current_price,
            "currency": other.currency,
            "status": other.status,
            "dedup_confidence": other.dedup_confidence,
        }
        for other in other_listings
    ]

    base = _summary(listing, area.name if area else "")
    return ListingDetail(
        **base.model_dump(),
        description=listing.description,
        address_text=prop.address_text,
        bathrooms=prop.bathrooms,
        floor=prop.floor,
        year_built=prop.year_built,
        features=prop.features,
        agency_name=listing.agency.name if listing.agency else None,
        source_code=listing.provider.code,
        source_name=listing.provider.name,
        dedup_confidence=listing.dedup_confidence,
        first_seen_at=listing.first_seen_at,
        last_seen_at=listing.last_seen_at,
        price_history=[
            PricePoint(observed_at=o.observed_at, price=o.price, currency=o.currency)
            for o in observations
        ],
        versions=[_version_out(v) for v in listing.versions],
        comparables=comparables,
        estimate=estimate,
        deviation_from_area_pct=deviation,
        duplicate_listings=duplicate_listings,
    )


@router.get("/{listing_id}/history", response_model=list[VersionOut])
def get_listing_history(listing_id: str, db: DbDep) -> list[VersionOut]:
    listing = db.get(PropertyListing, listing_id)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return [_version_out(v) for v in listing.versions]


@router.get("/{listing_id}/versions/{version_number}/snapshot")
def get_listing_version_snapshot(listing_id: str, version_number: int, db: DbDep) -> dict:
    """Raw immutable snapshot as stored in object storage at capture time
    (see services/storage.py) — provenance/audit trail, not a live view."""
    version = db.scalar(
        select(ListingVersion).where(
            ListingVersion.listing_id == listing_id, ListingVersion.version_number == version_number
        )
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    data = get_snapshot(version.snapshot_key)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found in storage")
    return {"storage_key": version.snapshot_key, "content": json.loads(data)}
