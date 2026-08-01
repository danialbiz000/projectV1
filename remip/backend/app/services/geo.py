"""Pure-Python geospatial primitives shared across services.

Spatial filtering (radius, polygon) runs here in Python rather than via
PostGIS SQL so it behaves identically on SQLite (local dev/tests) and
PostgreSQL (docker-compose). PostGIS itself is provisioned and its extension
enabled (see db/base.py) so indexed geometry columns (ST_DWithin, ST_Contains)
can replace this layer once listing volume outgrows in-process filtering —
see docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km. Accurate at any scale (unlike the flat
    equirectangular approximation, which only holds at neighborhood scale)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting (PNPOLY) test. polygon is a list of (lon, lat) vertices;
    does not need to be explicitly closed (last point == first)."""
    if len(polygon) < 3:
        return False
    inside = False
    x, y = lon, lat
    x1, y1 = polygon[-1]
    for x2, y2 in polygon:
        if (y1 > y) != (y2 > y):
            x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_intersect:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def circle_polygon(lat: float, lon: float, radius_km: float, points: int = 48) -> list[list[float]]:
    """Approximate a circle of radius_km around (lat, lon) as a [lon, lat] ring,
    for rendering (e.g. a GeoJSON polygon) rather than for filtering."""
    lat_rad = math.radians(lat)
    coords: list[list[float]] = []
    for i in range(points + 1):
        angle = 2 * math.pi * i / points
        dlat = (radius_km / EARTH_RADIUS_KM) * math.cos(angle)
        dlon = (
            (radius_km / EARTH_RADIUS_KM)
            * math.sin(angle)
            / max(math.cos(lat_rad), 1e-6)
        )
        coords.append([lon + math.degrees(dlon), lat + math.degrees(dlat)])
    return coords
