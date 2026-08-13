"""Zone market-quality score (M7) — services/zone_quality.py. Reuses the
explanation engine's driver classification, so these tests mirror the
rising/falling/insufficient-history scenarios in test_explanation.py."""
from datetime import date

from app.models import MarketMetric
from app.services.explanation import MIN_MONTHS
from app.services.zone_quality import compute_market_score


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


def test_insufficient_history_returns_none():
    assert compute_market_score([_metric() for _ in range(MIN_MONTHS - 1)]) is None


def test_rising_market_scores_above_baseline():
    series = [
        _metric(
            active_listings=100 - i * 10,
            avg_days_on_market=90 - i * 8,
            avg_price_sqm=3000 + i * 60,
            price_reduction_share=0.10,
        )
        for i in range(MIN_MONTHS)
    ]
    result = compute_market_score(series)
    assert result is not None
    assert result["score"] > 50
    assert result["label"] == "mercato forte"


def test_falling_market_scores_below_baseline():
    series = [
        _metric(
            active_listings=100 + i * 15,
            avg_days_on_market=90 + i * 10,
            avg_price_sqm=3000 - i * 60,
            price_reduction_share=0.45,
        )
        for i in range(MIN_MONTHS)
    ]
    result = compute_market_score(series)
    assert result is not None
    assert result["score"] < 50
    assert result["label"] == "mercato debole"


def test_flat_market_stays_near_baseline():
    series = [_metric(avg_price_sqm=3000.0) for _ in range(MIN_MONTHS)]
    result = compute_market_score(series)
    assert result is not None
    assert 30 <= result["score"] <= 70


def test_score_is_bounded_0_100():
    series = [
        _metric(
            active_listings=100 - i * 20,
            avg_days_on_market=max(90 - i * 20, 5),
            avg_price_sqm=3000 + i * 200,
            price_reduction_share=0.02,
        )
        for i in range(24)
    ]
    result = compute_market_score(series)
    assert result is not None
    assert 0 <= result["score"] <= 100


def test_result_carries_drivers_and_disclosure_text():
    series = [_metric(avg_price_sqm=3000.0) for _ in range(MIN_MONTHS)]
    result = compute_market_score(series)
    assert result is not None
    assert "positive_drivers" in result and "negative_drivers" in result
    assert "qualità della vita" in result["limitations"]
