from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbDep
from app.api.v1.listings import descendant_area_ids
from app.models import AdministrativeArea, EconomicIndicator, MarketForecast, OmiZoneQuotation
from app.schemas.common import DataContext
from app.schemas.listing import AreaCompareRow
from app.services import explanation as explanation_service
from app.services import forecast as forecast_service
from app.services import market as market_service
from app.services import zone_quality as zone_quality_service

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


@router.get("/omi-quotations")
def omi_quotations(
    db: DbDep,
    area_id: str,
    listing_type: str = Query(default="sale", pattern="^(sale|rent)$"),
) -> dict:
    """Zone-level price bands ingested from the OMI-shaped adapter (M4),
    independent of the per-listing MarketMetric pipeline — a cross-check
    figure, not a replacement. See adapters/omi.py for why the values are
    illustrative rather than a verified live feed."""
    _area_or_404(db, area_id)
    rows = db.scalars(
        select(OmiZoneQuotation)
        .where(
            OmiZoneQuotation.area_id.in_(descendant_area_ids(db, area_id)),
            OmiZoneQuotation.listing_type == listing_type,
        )
        .order_by(OmiZoneQuotation.period.desc(), OmiZoneQuotation.zone_description)
    ).all()
    latest = rows[0] if rows else None
    return {
        "data": [
            {
                "area_id": r.area_id,
                "comune": r.comune,
                "zone_code": r.zone_code,
                "zone_description": r.zone_description,
                "property_type": r.property_type,
                "conservation_state": r.conservation_state,
                "period": r.period,
                "price_sqm_min": r.price_sqm_min,
                "price_sqm_max": r.price_sqm_max,
                "currency": r.currency,
            }
            for r in rows
        ],
        "data_context": DataContext(
            sources=["omi_it"],
            period=latest.period if latest else None,
            observations=len(rows),
            updated_at=latest.ingested_at if latest else None,
            quality=0.4,
            aggregation_level="zona OMI",
            methodology="Range compravendite/locazioni €/m² per zona OMI, tipologia e stato "
            "conservativo, da adapter dedicato (docs/ARCHITECTURE.md).",
            limitations="Valori illustrativi da fixture locale versionata, non da endpoint "
            "OMI live verificato (vedi docs/INTEGRATIONS.md). Copertura limitata alle zone "
            "demo configurate.",
            is_demo_data=True,
        ).model_dump(),
    }


@router.get("/economic-indicators")
def economic_indicators(db: DbDep, country: str = Query(default="IT", max_length=2)) -> dict:
    """Live macro indicators ingested from a real HTTP source (Eurostat
    House Price Index, M4) — no per-area coverage, national level only, and
    only as fresh as the last successful ingestion run (GET
    /admin/ingestion/jobs shows whether it has actually succeeded in this
    deployment). Unlike /market/omi-quotations, `is_demo_data` here is
    False: if a row exists, its value came from a real API response, not a
    fixture. See adapters/eurostat.py and docs/INTEGRATIONS.md."""
    rows = db.scalars(
        select(EconomicIndicator)
        .where(EconomicIndicator.country_code == country.upper())
        .order_by(EconomicIndicator.indicator_code, EconomicIndicator.period.desc())
    ).all()
    latest = rows[0] if rows else None
    return {
        "data": [
            {
                "country_code": r.country_code,
                "indicator_code": r.indicator_code,
                "indicator_name": r.indicator_name,
                "period": r.period,
                "value": r.value,
                "unit": r.unit,
            }
            for r in rows
        ],
        "data_context": DataContext(
            sources=["eurostat_hpi"],
            period=latest.period if latest else None,
            observations=len(rows),
            updated_at=latest.ingested_at if latest else None,
            quality=0.85 if rows else None,
            aggregation_level="country",
            methodology="Eurostat prc_hpi_q (House Price Index), chiamata HTTP live "
            "all'API pubblica Eurostat, nessuna chiave richiesta.",
            limitations="Nessun dato se l'ultima ingestion non è mai riuscita (nessun "
            "fallback a valori sintetici, per design) — vedi GET /admin/ingestion/jobs. "
            "Copertura nazionale, non per città/zona.",
            is_demo_data=False,
        ).model_dump(),
    }


@router.get("/compare-areas", response_model=list[AreaCompareRow])
def compare_areas(
    db: DbDep,
    area_ids: list[str] = Query(..., min_length=2, max_length=4),
    listing_type: str = Query(default="sale", pattern="^(sale|rent)$"),
) -> list[AreaCompareRow]:
    """Side-by-side KPIs for 2-4 areas — same figures as /market/summary for
    a single area, so a comparison view can be built from data already
    proven correct there."""
    if len(set(area_ids)) != len(area_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate area_ids")
    rows: list[AreaCompareRow] = []
    for area_id in area_ids:
        area = _area_or_404(db, area_id)
        trend, score = market_service.price_trend_and_score(db, area_id, listing_type)
        rows.append(
            AreaCompareRow(
                **market_service.summarize(db, area, listing_type),
                market_score=score,
                price_trend=trend,
            )
        )
    return rows


@router.get("/explanation")
def market_explanation(
    db: DbDep,
    area_id: str,
    listing_type: str = Query(default="sale", pattern="^(sale|rent)$"),
) -> dict:
    """Why the market looks like it's rising/falling/flat (M5) — correlational
    drivers read off the observed metric series, never invented causality.
    See services/explanation.py."""
    area = _area_or_404(db, area_id)
    series = market_service.get_series(db, area_id, listing_type)
    latest_hpi = db.scalar(
        select(EconomicIndicator)
        .where(
            EconomicIndicator.country_code == "IT",
            EconomicIndicator.indicator_code == "house_price_index_rch_a",
        )
        .order_by(EconomicIndicator.period.desc())
        .limit(1)
    )
    result = explanation_service.explain_trend(series, latest_hpi)
    result["market_score"] = zone_quality_service.compute_market_score(series, latest_hpi)
    return {
        "data": result,
        "data_context": _context(
            series,
            area,
            "Driver correlazionali dagli ultimi "
            f"{explanation_service.MIN_MONTHS} mesi della serie MarketMetric dell'area; "
            "nessuna relazione causale è affermata (vedi 'alternative_explanations').",
            "Dati sintetici demo per l'area; il contesto nazionale (se presente) proviene "
            "da una fonte live separata — vedi 'national_context'.",
        ).model_dump(),
    }
