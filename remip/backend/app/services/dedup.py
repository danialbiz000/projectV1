"""Cross-source/cross-agency duplicate detection for physical properties.

When a new listing arrives, the platform must decide whether it describes a
*physical property* already known (e.g. republished by another agency) or a
genuinely new one. This module scores candidates and returns a confidence in
[0, 1]; callers decide the threshold. Nothing here merges data silently —
a match only changes which PhysicalProperty a new PropertyListing points to.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PhysicalProperty
from app.services.geo import haversine_km

MATCH_THRESHOLD = 0.75
CANDIDATE_RADIUS_KM = 0.3  # only compare properties within ~300m
SIZE_TOLERANCE = 0.1  # ±10%


@dataclass
class DuplicateCandidate:
    property: PhysicalProperty
    confidence: float
    reasons: list[str]


def _token_overlap(a: str, b: str) -> float:
    """Jaccard similarity over lowercase word tokens — cheap, dependency-free
    stand-in for real address matching (no geocoding/NLP service available)."""
    tokens_a = {t for t in a.lower().split() if len(t) > 2}
    tokens_b = {t for t in b.lower().split() if len(t) > 2}
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union) if union else 0.0


def score_candidate(
    *,
    lat: float,
    lon: float,
    size_sqm: float,
    rooms: int,
    address_text: str,
    candidate: PhysicalProperty,
) -> DuplicateCandidate:
    reasons: list[str] = []
    dist_km = haversine_km(lat, lon, candidate.lat, candidate.lon)
    geo_score = max(0.0, 1.0 - dist_km / CANDIDATE_RADIUS_KM)
    if geo_score > 0.5:
        reasons.append(f"distanza {dist_km * 1000:.0f}m")

    size_diff = abs(candidate.size_sqm - size_sqm) / max(size_sqm, 1)
    size_score = max(0.0, 1.0 - size_diff / SIZE_TOLERANCE)
    if size_score > 0.5:
        reasons.append(f"superficie {candidate.size_sqm}m² vs {size_sqm}m²")

    rooms_diff = abs(candidate.rooms - rooms)
    rooms_score = 1.0 if rooms_diff == 0 else max(0.0, 1.0 - rooms_diff / 3)

    address_score = _token_overlap(address_text, candidate.address_text)
    if address_score > 0.3:
        reasons.append("indirizzo simile")

    confidence = round(
        geo_score * 0.45 + size_score * 0.25 + rooms_score * 0.15 + address_score * 0.15, 3
    )
    return DuplicateCandidate(property=candidate, confidence=confidence, reasons=reasons)


def find_duplicate_property(
    db: Session,
    *,
    area_id: str,
    property_type: str,
    lat: float,
    lon: float,
    size_sqm: float,
    rooms: int,
    address_text: str,
    threshold: float = MATCH_THRESHOLD,
) -> DuplicateCandidate | None:
    """Best-scoring existing PhysicalProperty in the same area/type within a
    tight geo radius, or None if nothing clears the confidence threshold."""
    candidates = db.scalars(
        select(PhysicalProperty).where(
            PhysicalProperty.area_id == area_id,
            PhysicalProperty.property_type == property_type,
        )
    ).all()
    best: DuplicateCandidate | None = None
    for candidate in candidates:
        scored = score_candidate(
            lat=lat,
            lon=lon,
            size_sqm=size_sqm,
            rooms=rooms,
            address_text=address_text,
            candidate=candidate,
        )
        if scored.confidence >= threshold and (best is None or scored.confidence > best.confidence):
            best = scored
    return best
