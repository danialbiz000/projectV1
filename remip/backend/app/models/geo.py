from __future__ import annotations

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid


class Country(Base):
    """Per-country configuration: no hardcoded assumptions about Italy."""

    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)  # ISO 3166-1 alpha-2
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3))  # ISO 4217
    locale: Mapped[str] = mapped_column(String(10), default="en")
    unit_system: Mapped[str] = mapped_column(String(10), default="metric")
    # Ordered administrative levels for this country, e.g. IT:
    # ["region", "province", "city", "neighborhood"]
    admin_levels: Mapped[list] = mapped_column(JSON, default=list)


class AdministrativeArea(Base):
    __tablename__ = "administrative_areas"
    __table_args__ = (UniqueConstraint("country_code", "slug", name="uq_area_country_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), index=True)
    level: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    slug: Mapped[str] = mapped_column(String(200), index=True)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("administrative_areas.id"), nullable=True, index=True
    )
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)

    parent: Mapped[AdministrativeArea | None] = relationship(remote_side="AdministrativeArea.id")
