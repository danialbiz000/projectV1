"""Market analytics over pre-aggregated monthly MarketMetric rows."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdministrativeArea, MarketMetric
from app.schemas.listing import TrendPoint
from app.services.zone_quality import compute_market_score

CHANGE_WINDOWS_MONTHS = {"1m": 1, "3m": 3, "6m": 6, "12m": 12, "5y": 60, "10y": 120}
PRICE_TREND_MONTHS = 24


def get_series(
    db: Session, area_id: str, listing_type: str = "sale", months: int | None = None
) -> list[MarketMetric]:
    query = (
        select(MarketMetric)
        .where(MarketMetric.area_id == area_id, MarketMetric.listing_type == listing_type)
        .order_by(MarketMetric.period)
    )
    rows = list(db.scalars(query))
    return rows[-months:] if months else rows


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def compute_changes(series: list[MarketMetric]) -> dict[str, float | None]:
    """% change of avg price/sqm over standard windows; None when history is short."""
    changes: dict[str, float | None] = {}
    if not series:
        return {k: None for k in CHANGE_WINDOWS_MONTHS}
    latest = series[-1]
    by_offset = {_months_between(m.period, latest.period): m for m in series}
    for label, months in CHANGE_WINDOWS_MONTHS.items():
        past = by_offset.get(months)
        if past is None or past.avg_price_sqm <= 0:
            changes[label] = None
        else:
            changes[label] = round(
                (latest.avg_price_sqm - past.avg_price_sqm) / past.avg_price_sqm * 100, 2
            )
    return changes


def summarize(db: Session, area: AdministrativeArea, listing_type: str = "sale") -> dict[str, Any]:
    series = get_series(db, area.id, listing_type)
    if not series:
        return {"area_id": area.id, "available": False}
    latest = series[-1]
    return {
        "area_id": area.id,
        "area_name": area.name,
        "area_level": area.level,
        "available": True,
        "listing_type": listing_type,
        "period": latest.period.isoformat(),
        "avg_price": latest.avg_price,
        "median_price": latest.median_price,
        "avg_price_sqm": latest.avg_price_sqm,
        "median_price_sqm": latest.median_price_sqm,
        "active_listings": latest.active_listings,
        "new_listings": latest.new_listings,
        "removed_listings": latest.removed_listings,
        "avg_days_on_market": latest.avg_days_on_market,
        "price_reduction_share": latest.price_reduction_share,
        "avg_discount_pct": latest.avg_discount_pct,
        "rent_avg_sqm": latest.rent_avg_sqm,
        "gross_yield_pct": latest.gross_yield_pct,
        "currency": latest.currency,
        "changes_pct": compute_changes(series),
    }


def price_trend_and_score(
    db: Session, area_id: str, listing_type: str = "sale"
) -> tuple[list[TrendPoint], dict[str, Any] | None]:
    """Zone-level monthly €/m² series and the market-quality score derived
    from it (M7) — used to compare properties across different zones on
    equal footing, since a single listing rarely has enough of its own
    price history to chart meaningfully (see docs/PLAN.md M7 exit note)."""
    series = get_series(db, area_id, listing_type, months=PRICE_TREND_MONTHS)
    trend = [
        TrendPoint(period=m.period.isoformat(), avg_price_sqm=m.avg_price_sqm) for m in series
    ]
    return trend, compute_market_score(series)
