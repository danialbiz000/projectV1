from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbDep
from app.models import AdministrativeArea, Country
from app.schemas.listing import AreaOut

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/countries")
def list_countries(db: DbDep) -> list[dict]:
    countries = db.scalars(select(Country).order_by(Country.name)).all()
    return [
        {
            "code": c.code,
            "name": c.name,
            "currency": c.currency,
            "locale": c.locale,
            "unit_system": c.unit_system,
            "admin_levels": c.admin_levels,
        }
        for c in countries
    ]


@router.get("/areas", response_model=list[AreaOut])
def list_areas(
    db: DbDep,
    country: str = Query(default="IT", max_length=2),
    level: str | None = Query(default=None),
    parent_id: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=2, max_length=100),
) -> list[AdministrativeArea]:
    query = select(AdministrativeArea).where(AdministrativeArea.country_code == country.upper())
    if level:
        query = query.where(AdministrativeArea.level == level)
    if parent_id:
        query = query.where(AdministrativeArea.parent_id == parent_id)
    if q:
        query = query.where(AdministrativeArea.name.ilike(f"%{q}%"))
    return list(db.scalars(query.order_by(AdministrativeArea.name).limit(200)))


@router.get("/areas/{area_id}", response_model=AreaOut)
def get_area(area_id: str, db: DbDep) -> AdministrativeArea:
    area = db.get(AdministrativeArea, area_id)
    if area is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Area not found")
    return area
