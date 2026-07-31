"""Unit tests for core services and the adapter contract."""
import pytest

from app.adapters.base import AdapterError, BaseAdapter, SourceInfo
from app.adapters.demo import DemoAdapter
from app.core.security import hash_password, verify_password
from app.services.forecast import compute_forecasts
from app.services.versioning import classify_event


def test_password_hashing_roundtrip():
    stored = hash_password("s3curepassword")
    assert stored.startswith("pbkdf2_sha256$")
    assert "s3curepassword" not in stored
    assert verify_password("s3curepassword", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("anything", "garbage")


def test_demo_adapter_is_deterministic_and_deduplicated():
    a = DemoAdapter(seed=7, listings_per_neighborhood=3).run()
    b = DemoAdapter(seed=7, listings_per_neighborhood=3).run()
    assert [x.external_id for x in a] == [x.external_id for x in b]
    assert len({x.external_id for x in a}) == len(a)
    info = DemoAdapter().source_info()
    assert info.is_demo and info.tos_compliant


def test_non_compliant_adapter_cannot_be_enabled():
    class ScraperAdapter(BaseAdapter):
        def source_info(self):
            return SourceInfo(code="bad", name="Bad", kind="portal", tos_compliant=False)

        def fetch_raw(self):  # pragma: no cover
            return []

        def validate(self, record):  # pragma: no cover
            return True

        def normalize(self, record):  # pragma: no cover
            raise NotImplementedError

    with pytest.raises(AdapterError):
        ScraperAdapter(enabled=True)
    disabled = ScraperAdapter(enabled=False)
    assert disabled.run() == []


def test_classify_event_priorities():
    assert classify_event({"status": {"old": "active", "new": "removed"}}) == "listing_removed"
    assert classify_event({"price": {"old": 100, "new": 90}}) == "price_drop"
    assert classify_event({"price": {"old": 100, "new": 110}}) == "price_increase"
    assert classify_event({"description": {"old": "a", "new": "b"}}) == "listing_update"


class _FakeMetric:
    def __init__(self, sqm):
        self.avg_price_sqm = sqm


def test_forecast_needs_history_and_orders_scenarios():
    assert compute_forecasts([_FakeMetric(1000)] * 3) == []
    series = [_FakeMetric(1000 + 10 * i) for i in range(24)]
    forecasts = compute_forecasts(series)  # type: ignore[arg-type]
    assert [f["horizon_months"] for f in forecasts] == [3, 6, 12, 60, 120]
    for f in forecasts:
        assert f["low_change_pct"] <= f["base_change_pct"] <= f["high_change_pct"]
    rising = next(f for f in forecasts if f["horizon_months"] == 3)
    assert rising["base_change_pct"] > 0
    assert rising["drivers"][0]["evidence"] == "observed"
