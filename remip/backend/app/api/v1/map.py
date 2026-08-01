from __future__ import annotations

import math

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbDep
from app.api.v1.listings import descendant_area_ids
from app.models import AdministrativeArea, PhysicalProperty, PropertyListing
from app.schemas.map import MapPoint, MapSearchRequest
from app.services.geo import haversine_km, point_in_polygon

router = APIRouter(prefix="/map", tags=["map"])


def _radius_bbox(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / 111.0  # ~km per degree latitude
    dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def _polygon_bbox(polygon: list[list[float]]) -> tuple[float, float, float, float]:
    lons = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    return min(lons), min(lats), max(lons), max(lats)


@router.post("/search")
def search_map(body: MapSearchRequest, db: DbDep) -> dict:
    """Lightweight listing points for the map: markers, clustering and
    heatmap layers are all rendered client-side from this payload. Supports
    bounding-box, radius and freehand-polygon spatial filters (see
    docs/ARCHITECTURE.md for why these run in Python rather than PostGIS SQL)."""
    query = (
        select(PropertyListing)
        .join(PhysicalProperty, PropertyListing.property_id == PhysicalProperty.id)
        .where(
            PropertyListing.listing_type == body.listing_type,
            PropertyListing.status == body.status,
        )
    )
    if body.area_id:
        query = query.where(PhysicalProperty.area_id.in_(descendant_area_ids(db, body.area_id)))
    if body.property_type:
        query = query.where(PhysicalProperty.property_type == body.property_type)
    if body.min_price is not None:
        query = query.where(PropertyListing.current_price >= body.min_price)
    if body.max_price is not None:
        query = query.where(PropertyListing.current_price <= body.max_price)

    # SQL-level bounding-box pre-filter (cheap, index-friendly) ahead of any
    # exact Python-side radius/polygon test.
    bbox = body.bbox
    if body.radius:
        bbox_tuple = _radius_bbox(body.radius.lat, body.radius.lon, body.radius.radius_km)
    elif body.polygon:
        bbox_tuple = _polygon_bbox(body.polygon)
    elif bbox:
        bbox_tuple = (bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)
    else:
        bbox_tuple = None
    if bbox_tuple:
        min_lon, min_lat, max_lon, max_lat = bbox_tuple
        query = query.where(
            PhysicalProperty.lat >= min_lat,
            PhysicalProperty.lat <= max_lat,
            PhysicalProperty.lon >= min_lon,
            PhysicalProperty.lon <= max_lon,
        )

    candidates = list(db.scalars(query))

    if body.radius:
        candidates = [
            c
            for c in candidates
            if haversine_km(body.radius.lat, body.radius.lon, c.property.lat, c.property.lon)
            <= body.radius.radius_km
        ]
    if body.polygon:
        ring = [(v[0], v[1]) for v in body.polygon]
        candidates = [
            c for c in candidates if point_in_polygon(c.property.lat, c.property.lon, ring)
        ]

    total_matched = len(candidates)
    truncated = total_matched > body.limit
    points = [
        MapPoint(
            id=c.id,
            lat=c.property.lat,
            lon=c.property.lon,
            price=c.current_price,
            currency=c.currency,
            price_per_sqm=(
                round(c.current_price / c.property.size_sqm, 0) if c.property.size_sqm else None
            ),
            listing_type=c.listing_type,
            property_type=c.property.property_type,
            size_sqm=c.property.size_sqm,
            rooms=c.property.rooms,
        )
        for c in candidates[: body.limit]
    ]
    return {
        "items": [p.model_dump() for p in points],
        "total_matched": total_matched,
        "truncated": truncated,
        "data_context": {
            "sources": ["demo_it"],
            "period": None,
            "observations": total_matched,
            "updated_at": None,
            "quality": None,
            "aggregation_level": "listing",
            "methodology": "Filtro spaziale lato applicazione (bounding box SQL + test esatto "
            "in Python); nessuna estensione PostGIS richiesta per l'MVP.",
            "limitations": "Dati sintetici demo. Risultati troncati oltre il limite richiesto.",
            "is_demo_data": True,
        },
    }


@router.get("/areas-geo")
def areas_geo(db: DbDep, country: str = "IT", level: str = "neighborhood") -> list[dict]:
    """Centroids for a given administrative level, for map labels/heatmap
    aggregation when no listing-level detail is needed."""
    areas = db.scalars(
        select(AdministrativeArea).where(
            AdministrativeArea.country_code == country.upper(),
            AdministrativeArea.level == level,
        )
    ).all()
    return [
        {"id": a.id, "name": a.name, "lat": a.centroid_lat, "lon": a.centroid_lon}
        for a in areas
    ]
