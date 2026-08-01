from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utcnow


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="La mia watchlist")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list[WatchlistItem]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlists.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # listing | area
    listing_id: Mapped[str | None] = mapped_column(
        ForeignKey("property_listings.id"), nullable=True, index=True
    )
    area_id: Mapped[str | None] = mapped_column(
        ForeignKey("administrative_areas.id"), nullable=True, index=True
    )
    note: Mapped[str] = mapped_column(String(1000), default="")
    initial_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    thresholds: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. {"price_drop_pct": 5}
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # dedup_key prevents duplicate notifications for the same event+user
        UniqueConstraint("user_id", "dedup_key", name="uq_notification_user_dedup"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))  # price_drop, price_increase, removed, ...
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(String(2000), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    dedup_key: Mapped[str] = mapped_column(String(200))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationPreference(Base):
    """One row per user. Absence of a row means "all defaults" (instant,
    nothing muted) — created lazily on first read/write, not at registration,
    so most users never get a row until they actually change something."""

    __tablename__ = "notification_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    frequency: Mapped[str] = mapped_column(String(20), default="instant")
    # instant | daily_digest | weekly_digest
    muted_types: Mapped[list] = mapped_column(JSON, default=list)  # notification "type" values
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
