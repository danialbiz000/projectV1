from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class DataIngestionJob(Base):
    """One run of an adapter, whether triggered by the scheduler or an admin.

    Implements the entity deferred in docs/DATA_MODEL.md §"entità
    pianificate" — now real because M4 introduces recurring ingestion.
    """

    __tablename__ = "data_ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_code: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|failed
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual|scheduled|seed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")


class OmiZoneQuotation(Base):
    """A published price-band observation, shaped after OMI's real semestral
    exports (comune / zona / tipologia / stato / compravendite-locazioni
    min-max €/m²) rather than a per-listing record. See adapters/omi.py for
    why the values here are illustrative, not a live feed."""

    __tablename__ = "omi_zone_quotations"
    __table_args__ = (
        UniqueConstraint(
            "area_id",
            "zone_code",
            "property_type",
            "conservation_state",
            "period",
            "listing_type",
            name="uq_omi_quotation_natural_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    area_id: Mapped[str | None] = mapped_column(
        ForeignKey("administrative_areas.id"), nullable=True, index=True
    )
    provider_id: Mapped[str] = mapped_column(ForeignKey("data_providers.id"), index=True)
    comune: Mapped[str] = mapped_column(String(200))
    zone_code: Mapped[str] = mapped_column(String(20))
    zone_description: Mapped[str] = mapped_column(String(200))
    property_type: Mapped[str] = mapped_column(String(40))
    conservation_state: Mapped[str] = mapped_column(String(30))
    period: Mapped[str] = mapped_column(String(10), index=True)  # e.g. "2026-1"
    listing_type: Mapped[str] = mapped_column(String(10))  # sale | rent
    price_sqm_min: Mapped[float] = mapped_column(Float)
    price_sqm_max: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    source_code: Mapped[str] = mapped_column(String(50), default="omi_it")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EconomicIndicator(Base):
    """A genuinely live macro indicator (M4): unlike OmiZoneQuotation, values
    here come from a real HTTP call to a public statistical API — no
    synthetic fallback. See adapters/eurostat.py for the (unverified from
    this sandbox — see docs/INTEGRATIONS.md) live fetch, and
    jobs/ingestion.py for why a failed fetch leaves no row rather than a
    fabricated one."""

    __tablename__ = "economic_indicators"
    __table_args__ = (
        UniqueConstraint(
            "country_code", "indicator_code", "period", name="uq_economic_indicator_period"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    indicator_code: Mapped[str] = mapped_column(String(50), index=True)
    indicator_name: Mapped[str] = mapped_column(String(200))
    period: Mapped[str] = mapped_column(String(10), index=True)  # e.g. "2025-Q3"
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    source_code: Mapped[str] = mapped_column(String(50), default="eurostat_hpi")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
