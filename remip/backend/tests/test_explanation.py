"""Unit tests for the market-trend explanation engine (services/explanation.py)
and an integration test for GET /market/explanation."""
from datetime import date

from app.models import MarketMetric
from app.services.explanation import MIN_MONTHS, explain_trend


def _metric(**overrides) -> MarketMetric:
    defaults = dict(
        area_id="area-x",
        period=date(2026, 1, 1),
        listing_type="sale",
        avg_price=300000.0,
        median_price=290000.0,
        avg_price_sqm=3000.0,
        median_price_sqm=2900.0,
        active_listings=100,
        new_listings=10,
        removed_listings=8,
        avg_days_on_market=90.0,
        price_reduction_share=0.20,
        avg_discount_pct=5.0,
        rent_avg_sqm=15.0,
        gross_yield_pct=5.0,
        sample_size=100,
        data_quality=0.99,
        currency="EUR",
        source_code="demo_it",
    )
    defaults.update(overrides)
    return MarketMetric(**defaults)


def test_insufficient_history_reports_unavailable():
    result = explain_trend([_metric() for _ in range(MIN_MONTHS - 1)])
    assert result["available"] is False
    assert "Servono almeno" in result["reason"]


def test_rising_market_with_shrinking_inventory_and_faster_sales():
    series = [
        _metric(
            active_listings=100 - i * 10,
            avg_days_on_market=90 - i * 8,
            avg_price_sqm=3000 + i * 60,
            price_reduction_share=0.10,
        )
        for i in range(MIN_MONTHS)
    ]
    result = explain_trend(series)
    assert result["available"] is True
    assert result["observed_trend"] == "in crescita"
    assert result["price_change_pct"] > 0
    positive_names = {d["name"] for d in result["positive_drivers"]}
    assert "Riduzione dell'offerta attiva" in positive_names
    assert "Tempi di vendita in diminuzione" in positive_names
    assert result["negative_drivers"] == []
    assert result["evidence_strength"] in ("moderata", "debole")
    assert "MarketMetric.active_listings" in result["sources"]
    assert len(result["uncertain_elements"]) > 0
    assert "causali" in result["alternative_explanations"]


def test_falling_market_with_growing_inventory_and_heavy_discounts():
    series = [
        _metric(
            active_listings=100 + i * 15,
            avg_days_on_market=90 + i * 10,
            avg_price_sqm=3000 - i * 60,
            price_reduction_share=0.45,
        )
        for i in range(MIN_MONTHS)
    ]
    result = explain_trend(series)
    assert result["observed_trend"] == "in calo"
    negative_names = {d["name"] for d in result["negative_drivers"]}
    assert "Aumento dell'offerta attiva" in negative_names
    assert "Tempi di vendita in aumento" in negative_names
    assert "Ampia quota di annunci con ribasso" in negative_names
    assert result["positive_drivers"] == []


def test_flat_market_reports_stable_trend():
    series = [_metric(avg_price_sqm=3000.0) for _ in range(MIN_MONTHS)]
    result = explain_trend(series)
    assert result["observed_trend"] == "stabile"


def test_national_context_included_only_when_present():
    series = [_metric() for _ in range(MIN_MONTHS)]
    assert explain_trend(series, latest_national_hpi=None)["national_context"] is None

    class FakeIndicator:
        indicator_name = "House Price Index"
        period = "2026-Q1"
        value = 119.2
        unit = "pct_change_yoy"
        source_code = "eurostat_hpi"

    context = explain_trend(series, latest_national_hpi=FakeIndicator())["national_context"]
    assert context["is_demo_data"] is False
    assert context["period"] == "2026-Q1"


def test_market_explanation_endpoint(client):
    cities = client.get("/api/v1/geo/areas", params={"level": "city"}).json()
    milano_id = next(c["id"] for c in cities if c["name"] == "Milano")
    response = client.get("/api/v1/market/explanation", params={"area_id": milano_id})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["available"] is True
    assert body["data"]["observed_trend"] in ("in crescita", "in calo", "stabile")
    assert body["data_context"]["is_demo_data"] is True


def test_market_explanation_unknown_area_404(client):
    assert client.get("/api/v1/market/explanation", params={"area_id": "nope"}).status_code == 404
