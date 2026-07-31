from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AreaOut(BaseModel):
    id: str
    country_code: str
    level: str
    name: str
    slug: str
    parent_id: str | None
    centroid_lat: float
    centroid_lon: float
    population: int | None

    model_config = {"from_attributes": True}


class ListingSummary(BaseModel):
    id: str
    title: str
    listing_type: str
    status: str
    current_price: float
    currency: str
    price_per_sqm: float | None
    size_sqm: float
    rooms: int
    property_type: str
    energy_class: str | None
    area_id: str
    area_name: str
    lat: float
    lon: float
    published_at: datetime
    days_on_market: int
    photos_count: int
    is_demo_data: bool = True


class VersionOut(BaseModel):
    version_number: int
    captured_at: datetime
    price: float
    status: str
    diff: dict[str, Any]

    model_config = {"from_attributes": True}


class PricePoint(BaseModel):
    observed_at: datetime
    price: float
    currency: str


class ListingDetail(ListingSummary):
    description: str
    address_text: str
    bathrooms: int
    floor: int | None
    year_built: int | None
    features: dict[str, Any]
    agency_name: str | None
    source_code: str
    source_name: str
    dedup_confidence: float
    first_seen_at: datetime
    last_seen_at: datetime
    price_history: list[PricePoint]
    versions: list[VersionOut]
    comparables: list[dict[str, Any]]
    estimate: dict[str, Any] | None
    deviation_from_area_pct: float | None


class WatchlistItemIn(BaseModel):
    kind: str = "listing"  # listing | area
    listing_id: str | None = None
    area_id: str | None = None
    note: str = ""
    thresholds: dict[str, Any] = {}
    notify: bool = True


class WatchlistItemOut(BaseModel):
    id: str
    kind: str
    listing_id: str | None
    area_id: str | None
    note: str
    initial_price: float | None
    thresholds: dict[str, Any]
    notify: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    items: list[WatchlistItemOut]

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    payload: dict[str, Any]
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SimulateUpdateRequest(BaseModel):
    """Admin/demo endpoint: apply a change to a listing as if a source sent it."""

    listing_id: str
    changes: dict[str, Any]
