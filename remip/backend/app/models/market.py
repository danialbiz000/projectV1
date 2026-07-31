from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class MarketMetric(Base):
    """Monthly aggregated market indicators for an administrative area."""

    __tablename__ = "market_metrics"
    __table_args__ = (
        UniqueConstraint("area_id", "period", "listing_type", name="uq_metric_area_period_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    area_id: Mapped[str] = mapped_column(ForeignKey("administrative_areas.id"), index=True)
    period: Mapped[date] = mapped_column(Date, index=True)  # first day of month
    listing_type: Mapped[str] = mapped_column(String(10), default="sale")
    avg_price: Mapped[float] = mapped_column(Float)
    median_price: Mapped[float] = mapped_column(Float)
    avg_price_sqm: Mapped[float] = mapped_column(Float)
    median_price_sqm: Mapped[float] = mapped_column(Float)
    active_listings: Mapped[int] = mapped_column(Integer)
    new_listings: Mapped[int] = mapped_column(Integer)
    removed_listings: Mapped[int] = mapped_column(Integer)
    avg_days_on_market: Mapped[float] = mapped_column(Float)
    price_reduction_share: Mapped[float] = mapped_column(Float)  # 0..1 of active listings
    avg_discount_pct: Mapped[float] = mapped_column(Float)  # vs initial asking price
    rent_avg_sqm: Mapped[float] = mapped_column(Float)  # EUR/sqm/month
    gross_yield_pct: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
    data_quality: Mapped[float] = mapped_column(Float, default=1.0)  # 0..1
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    source_code: Mapped[str] = mapped_column(String(50), default="")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketForecast(Base):
    __tablename__ = "market_forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    area_id: Mapped[str] = mapped_column(ForeignKey("administrative_areas.id"), index=True)
    listing_type: Mapped[str] = mapped_column(String(10), default="sale")
    horizon_months: Mapped[int] = mapped_column(Integer)  # 3, 6, 12, 60, 120
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    base_change_pct: Mapped[float] = mapped_column(Float)
    low_change_pct: Mapped[float] = mapped_column(Float)
    high_change_pct: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)  # 0..1
    method: Mapped[str] = mapped_column(String(50))  # linear_trend | structural_scenario
    model_version: Mapped[str] = mapped_column(String(20), default="baseline-0.1")
    drivers: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[str] = mapped_column(Text, default="")
