import pytest


@pytest.fixture(scope="module")
def milano_id(client):
    cities = client.get("/api/v1/geo/areas", params={"level": "city"}).json()
    return next(c["id"] for c in cities if c["name"] == "Milano")


def test_market_summary(client, milano_id):
    response = client.get("/api/v1/market/summary", params={"area_id": milano_id})
    assert response.status_code == 200
    body = response.json()
    data, context = body["data"], body["data_context"]
    assert data["available"] is True
    assert data["avg_price_sqm"] > 0
    assert data["gross_yield_pct"] > 0
    # multi-period changes: 1/3/6/12m available with 36 months of history
    for window in ("1m", "3m", "6m", "12m"):
        assert data["changes_pct"][window] is not None
    assert data["changes_pct"]["10y"] is None  # not enough history → declared, not invented
    # transparency block is mandatory
    assert context["is_demo_data"] is True
    assert context["sources"] == ["demo_it"]
    assert context["observations"] > 0
    assert context["period"]


def test_market_metrics_series(client, milano_id):
    body = client.get(
        "/api/v1/market/metrics", params={"area_id": milano_id, "months": 36}
    ).json()
    series = body["data"]
    assert len(series) == 36
    periods = [m["period"] for m in series]
    assert periods == sorted(periods)
    assert all(m["sample_size"] > 0 for m in series)


def test_forecast_scenarios(client, milano_id):
    body = client.get("/api/v1/market/forecast", params={"area_id": milano_id}).json()
    forecasts = body["data"]
    assert [f["horizon_months"] for f in forecasts] == [3, 6, 12, 60, 120]
    for f in forecasts:
        s = f["scenarios"]
        assert s["negative"] <= s["base"] <= s["positive"]
        assert 0 < f["confidence"] <= 1
        assert f["drivers"] and f["limitations"]
    short = next(f for f in forecasts if f["horizon_months"] == 3)
    structural = next(f for f in forecasts if f["horizon_months"] == 60)
    # different horizons must use different methods (brief requirement)
    assert short["method"] == "linear_trend"
    assert structural["method"] == "structural_scenario"
    assert structural["confidence"] < short["confidence"]


def test_market_unknown_area(client):
    assert client.get("/api/v1/market/summary", params={"area_id": "nope"}).status_code == 404
