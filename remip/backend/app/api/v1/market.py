from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbDep
from app.models import AdministrativeArea, MarketForecast
from app.schemas.common import DataContext
from app.services import forecast as forecast_service
from app.services import market as market_service

router = APIRouter(prefix="/market", tags=["market"])


def _area_or_404(db, area_id: str) -> AdministrativeArea:
    area = db.get(AdministrativeArea, area_id)
    if area is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Area not found")
    return area


def _context(series, area: AdministrativeArea, methodology: str, limitations: str) -> DataContext:
    latest = series[-1] if series else None
    return DataContext(
        sources=[latest.source_code] if latest else [],
        period=(
            f"{series[0].period.isoformat()} → {latest.period.isoformat()}" if latest else None
        ),
        observations=sum(m.sample_size for m in series) if series else 0,
        updated_at=latest.computed_at if latest else None,
        quality=latest.data_quality if latest else None,
        aggregation_level=area.level,
        methodology=methodology,
        limitations=limitations,
        is_demo_data=True,
    )


@router.get("/summary")
def market_summary(
    db: DbDep,
    area_id: str,
    listing_type: str = Query(default="sale", pattern="^(sale|rent)$"),
) -> dict:
    area = _area_or_404(db, area_id)
    series = market_service.get_series(db, area_id, listing_type)
    return {
        "data": market_service.summarize(db, area, listing_type),
        "data_context": _context(
            series,
            area,
            "Aggregazione mensile di annunci attivi (media/mediana); variazioni % su €/m² medio.",
            "Dati sintetici demo. Le variazioni multi-periodo richiedono storico sufficiente.",
        ).model_dump(),
    }


@router.get("/metrics")
def market_metrics(
    db: DbDep,
    area_id: str,
    listing_type: str = Query(default="sale", pattern="^(sale|rent)$"),
    months: int = Query(default=36, ge=1, le=120),
) -> dict:
    area = _area_or_404(db, area_id)
    series = market_service.get_series(db, area_id, listing_type, months=months)
    return {
        "data": [
            {
                "period": m.period.isoformat(),
                "avg_price": m.avg_price,
                "median_price": m.median_price,
                "avg_price_sqm": m.avg_price_sqm,
                "median_price_sqm": m.median_price_sqm,
                "active_listings": m.active_listings,
                "new_listings": m.new_listings,
                "removed_listings": m.removed_listings,
                "avg_days_on_market": m.avg_days_on_market,
                "price_reduction_share": m.price_reduction_share,
                "avg_discount_pct": m.avg_discount_pct,
                "rent_avg_sqm": m.rent_avg_sqm,
                "gross_yield_pct": m.gross_yield_pct,
                "sample_size": m.sample_size,
                "currency": m.currency,
            }
            for m in series
        ],
        "data_context": _context(
            series,
            area,
            "Serie mensile aggregata per area amministrativa.",
            "Dati sintetici demo.",
        ).model_dump(),
    }


@router.get("/forecast")
def market_forecast(
    db: DbDep,
    area_id: str,
    listing_type: str = Query(default="sale", pattern="^(sale|rent)$"),
) -> dict:
    area = _area_or_404(db, area_id)
    forecasts = db.scalars(
        select(MarketForecast)
        .where(MarketForecast.area_id == area_id, MarketForecast.listing_type == listing_type)
        .order_by(MarketForecast.horizon_months)
    ).all()
    series = market_service.get_series(db, area_id, listing_type)
    return {
        "data": [
            {
                "horizon_months": f.horizon_months,
                "method": f.method,
                "model_version": f.model_version,
                "computed_at": f.computed_at.isoformat(),
                "scenarios": {
                    "negative": f.low_change_pct,
                    "base": f.base_change_pct,
                    "positive": f.high_change_pct,
                },
                "confidence": f.confidence,
                "drivers": f.drivers,
                "limitations": f.limitations,
            }
            for f in forecasts
        ],
        "data_context": _context(
            series,
            area,
            f"Orizzonti brevi: trend lineare OLS su {forecast_service.TREND_WINDOW} mesi. "
            "Orizzonti 5-10 anni: scenari strutturali (non statistici).",
            "Previsioni baseline dimostrative su dati demo: non costituiscono consulenza "
            "finanziaria. Accuratezza storica non ancora disponibile (modello baseline-0.1).",
        ).model_dump(),
    }
