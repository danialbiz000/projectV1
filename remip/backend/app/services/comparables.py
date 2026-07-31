"""Basic comparable search: same area and property type, similar size.

Returns listings ranked by a transparent similarity score (size, rooms,
distance). Persisted valuations arrive in M5; here everything is computed
on the fly and clearly bounded.
"""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PhysicalProperty, PropertyListing

SIZE_TOLERANCE = 0.35  # ±35%
MAX_RESULTS = 8


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Equirectangular approximation: fine at neighborhood scale.
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * 6371.0


def similarity_score(subject: PhysicalProperty, other: PhysicalProperty) -> float:
    size_diff = abs(other.size_sqm - subject.size_sqm) / max(subject.size_sqm, 1)
    rooms_diff = abs((other.rooms or 0) - (subject.rooms or 0))
    dist = _distance_km(subject.lat, subject.lon, other.lat, other.lon)
    score = 1.0 - min(size_diff, 1.0) * 0.5 - min(rooms_diff / 4, 1.0) * 0.25
    score -= min(dist / 5.0, 1.0) * 0.25
    return round(max(score, 0.0), 3)


def find_comparables(db: Session, listing: PropertyListing) -> list[dict[str, Any]]:
    subject = listing.property
    low, high = subject.size_sqm * (1 - SIZE_TOLERANCE), subject.size_sqm * (1 + SIZE_TOLERANCE)
    candidates = db.scalars(
        select(PropertyListing)
        .join(PhysicalProperty, PropertyListing.property_id == PhysicalProperty.id)
        .where(
            PropertyListing.id != listing.id,
            PropertyListing.listing_type == listing.listing_type,
            PropertyListing.status == "active",
            PhysicalProperty.area_id == subject.area_id,
            PhysicalProperty.property_type == subject.property_type,
            PhysicalProperty.size_sqm >= low,
            PhysicalProperty.size_sqm <= high,
        )
    ).all()
    scored: list[dict[str, Any]] = [
        {
            "listing_id": c.id,
            "title": c.title,
            "price": c.current_price,
            "currency": c.currency,
            "size_sqm": c.property.size_sqm,
            "rooms": c.property.rooms,
            "price_per_sqm": round(c.current_price / max(c.property.size_sqm, 1), 0),
            "similarity": similarity_score(subject, c.property),
        }
        for c in candidates
    ]
    scored.sort(key=lambda item: -float(item["similarity"]))
    return scored[:MAX_RESULTS]


def estimate_value(comparables: list[dict[str, Any]], size_sqm: float) -> dict[str, Any] | None:
    """Range estimate from comparables' price/sqm. Never a single certain value."""
    if len(comparables) < 3:
        return None
    per_sqm = sorted(float(c["price_per_sqm"]) for c in comparables)
    mid = per_sqm[len(per_sqm) // 2]
    low, high = per_sqm[0], per_sqm[-1]
    return {
        "estimated_value": round(mid * size_sqm, 0),
        "range_low": round(low * size_sqm, 0),
        "range_high": round(high * size_sqm, 0),
        "method": "comparable_median_price_sqm",
        "n_comparables": len(comparables),
        "confidence": round(min(0.3 + 0.05 * len(comparables), 0.7), 2),
        "assumptions": "Stima da mediana €/m² dei comparabili attivi nella stessa zona; "
        "non considera stato interno, piano, esposizione. Intervallo = min/max osservati.",
    }
