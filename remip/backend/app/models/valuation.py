from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class Valuation(Base):
    """A point-in-time valuation snapshot for a listing.

    Deliberately not written on every page view: a valuation is an explicit
    action (POST /listings/{id}/valuations), like an appraisal, not a
    side-effect of browsing — otherwise this table would grow unboundedly
    with no added signal. See services/comparables.py for the underlying
    (still on-the-fly, never-certain) estimation logic.
    """

    __tablename__ = "valuations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("property_listings.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    estimated_value: Mapped[float] = mapped_column(Float)
    range_low: Mapped[float] = mapped_column(Float)
    range_high: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    method: Mapped[str] = mapped_column(String(50))
    n_comparables: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)  # 0..1
    assumptions: Mapped[str] = mapped_column(Text, default="")
