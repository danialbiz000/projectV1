from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utcnow


class DataProvider(Base):
    __tablename__ = "data_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))  # demo | open_data | commercial | portal
    tos_compliant: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    last_ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    provider_id: Mapped[str | None] = mapped_column(
        ForeignKey("data_providers.id"), nullable=True
    )


class PhysicalProperty(Base):
    """The physical real-estate asset, independent from any single listing."""

    __tablename__ = "physical_properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    area_id: Mapped[str] = mapped_column(ForeignKey("administrative_areas.id"), index=True)
    address_text: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    property_type: Mapped[str] = mapped_column(String(40), index=True)  # apartment, villa, ...
    size_sqm: Mapped[float] = mapped_column(Float)
    rooms: Mapped[int] = mapped_column(Integer)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    energy_class: Mapped[str | None] = mapped_column(String(3), nullable=True)
    features: Mapped[dict] = mapped_column(JSON, default=dict)  # elevator, balcony, garage...


class PropertyListing(Base):
    __tablename__ = "property_listings"
    __table_args__ = (
        UniqueConstraint("provider_id", "source_external_id", name="uq_listing_provider_ext"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("physical_properties.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("data_providers.id"), index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), nullable=True)
    source_external_id: Mapped[str] = mapped_column(String(100))
    listing_type: Mapped[str] = mapped_column(String(10), index=True)  # sale | rent
    status: Mapped[str] = mapped_column(String(20), index=True, default="active")
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    current_price: Mapped[float] = mapped_column(Float, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    photos_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Confidence that cross-source listings mapped to the same physical property
    # actually refer to it (1.0 for demo data, computed by dedup service later).
    dedup_confidence: Mapped[float] = mapped_column(Float, default=1.0)

    property: Mapped[PhysicalProperty] = relationship()
    provider: Mapped[DataProvider] = relationship()
    agency: Mapped[Agency | None] = relationship()
    versions: Mapped[list[ListingVersion]] = relationship(
        back_populates="listing", order_by="ListingVersion.version_number"
    )


class ListingVersion(Base):
    __tablename__ = "listing_versions"
    __table_args__ = (
        UniqueConstraint("listing_id", "version_number", name="uq_version_listing_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("property_listings.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    price: Mapped[float] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    photos_count: Mapped[int] = mapped_column(Integer, default=0)
    size_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    energy_class: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    # Field-by-field diff vs the previous version: {field: {"old": x, "new": y}}
    diff: Mapped[dict] = mapped_column(JSON, default=dict)
    # Immutable raw snapshot in object storage (s3://... or file://...), M4.
    snapshot_key: Mapped[str] = mapped_column(String(300), default="")

    listing: Mapped[PropertyListing] = relationship(back_populates="versions")


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("property_listings.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    source_code: Mapped[str] = mapped_column(String(50), default="")
