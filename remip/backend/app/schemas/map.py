from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class BoundingBox(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class RadiusFilter(BaseModel):
    lat: float
    lon: float
    radius_km: float = Field(gt=0, le=100)


class MapSearchRequest(BaseModel):
    area_id: str | None = None
    listing_type: str = Field(default="sale", pattern="^(sale|rent)$")
    status: str = "active"
    property_type: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    bbox: BoundingBox | None = None
    radius: RadiusFilter | None = None
    # Polygon ring as [[lon, lat], ...]; does not need to be explicitly closed.
    polygon: list[list[float]] | None = None
    limit: int = Field(default=500, ge=1, le=2000)

    @model_validator(mode="after")
    def _validate_polygon(self) -> MapSearchRequest:
        if self.polygon is not None:
            if len(self.polygon) < 3:
                raise ValueError("polygon must have at least 3 vertices")
            if any(len(v) != 2 for v in self.polygon):
                raise ValueError("polygon vertices must be [lon, lat] pairs")
        return self


class MapPoint(BaseModel):
    id: str
    lat: float
    lon: float
    price: float
    currency: str
    price_per_sqm: float | None
    listing_type: str
    property_type: str
    size_sqm: float
    rooms: int
