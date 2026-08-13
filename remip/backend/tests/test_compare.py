import pytest


def test_compare_listings(client):
    items = client.get("/api/v1/listings", params={"limit": 3}).json()["items"]
    ids = [i["id"] for i in items]
    response = client.post("/api/v1/listings/compare", json={"listing_ids": ids})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == len(ids)
    assert [r["id"] for r in rows] == ids
    for row in rows:
        assert "deviation_from_area_pct" in row
        assert "estimate" in row
        assert "price_trend" in row and isinstance(row["price_trend"], list)
        if row["price_trend"]:
            assert {"period", "avg_price_sqm"} <= row["price_trend"][0].keys()
        # market_score is None when there isn't enough monthly history yet,
        # otherwise a dict with the same shape as GET /market/explanation's
        assert row["market_score"] is None or {"score", "label"} <= row["market_score"].keys()


def test_compare_listings_too_few(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    response = client.post("/api/v1/listings/compare", json={"listing_ids": [listing_id]})
    assert response.status_code == 422


def test_compare_listings_too_many(client):
    items = client.get("/api/v1/listings", params={"limit": 5}).json()["items"]
    ids = [i["id"] for i in items] * 2  # force > 4 by padding if fewer than 5 exist
    response = client.post("/api/v1/listings/compare", json={"listing_ids": ids[:5]})
    assert response.status_code == 422


def test_compare_listings_rejects_duplicates(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    response = client.post(
        "/api/v1/listings/compare", json={"listing_ids": [listing_id, listing_id]}
    )
    assert response.status_code == 400


def test_compare_listings_unknown_id_404(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    response = client.post(
        "/api/v1/listings/compare", json={"listing_ids": [listing_id, "nope"]}
    )
    assert response.status_code == 404


@pytest.fixture(scope="module")
def city_ids(client):
    cities = client.get("/api/v1/geo/areas", params={"level": "city"}).json()
    return [c["id"] for c in cities]


def test_compare_areas(client, city_ids):
    response = client.get(
        "/api/v1/market/compare-areas", params={"area_ids": city_ids[:3]}
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3
    assert all(r["available"] for r in rows)
    assert len({r["area_id"] for r in rows}) == 3
    for row in rows:
        assert "price_trend" in row and isinstance(row["price_trend"], list)
        assert row["market_score"] is None or {"score", "label"} <= row["market_score"].keys()


def test_compare_areas_too_few(client, city_ids):
    response = client.get("/api/v1/market/compare-areas", params={"area_ids": city_ids[:1]})
    assert response.status_code == 422


def test_compare_areas_rejects_duplicates(client, city_ids):
    response = client.get(
        "/api/v1/market/compare-areas",
        params={"area_ids": [city_ids[0], city_ids[0]]},
    )
    assert response.status_code == 400


def test_compare_areas_unknown_id_404(client, city_ids):
    response = client.get(
        "/api/v1/market/compare-areas", params={"area_ids": [city_ids[0], "nope"]}
    )
    assert response.status_code == 404
