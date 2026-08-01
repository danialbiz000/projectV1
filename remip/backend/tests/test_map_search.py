import pytest


@pytest.fixture(scope="module")
def milano_id(client):
    cities = client.get("/api/v1/geo/areas", params={"level": "city"}).json()
    return next(c["id"] for c in cities if c["name"] == "Milano")


MILANO_CENTER = {"lat": 45.4642, "lon": 9.1900}


def test_search_by_area(client, milano_id):
    response = client.post(
        "/api/v1/map/search", json={"area_id": milano_id, "listing_type": "sale", "limit": 500}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_matched"] > 0
    assert body["truncated"] is False
    assert all(p["listing_type"] == "sale" for p in body["items"])
    assert body["data_context"]["is_demo_data"] is True


def test_search_by_radius_is_subset_of_area(client, milano_id):
    area_result = client.post(
        "/api/v1/map/search", json={"area_id": milano_id, "limit": 1000}
    ).json()
    radius_result = client.post(
        "/api/v1/map/search",
        json={
            "area_id": milano_id,
            "radius": {**MILANO_CENTER, "radius_km": 2.0},
            "limit": 1000,
        },
    ).json()
    assert 0 < radius_result["total_matched"] <= area_result["total_matched"]
    for p in radius_result["items"]:
        assert p["listing_type"] == "sale"


def test_search_by_radius_excludes_far_city(client):
    # A narrow radius around Milan matches fewer listings than a wide one
    # that also reaches into Milan's surrounding scattered demo points.
    narrow = client.post(
        "/api/v1/map/search", json={"radius": {**MILANO_CENTER, "radius_km": 2.0}, "limit": 1000}
    ).json()
    wide = client.post(
        "/api/v1/map/search",
        json={"radius": {**MILANO_CENTER, "radius_km": 50.0}, "limit": 2000},
    ).json()
    assert narrow["total_matched"] > 0
    assert wide["total_matched"] >= narrow["total_matched"]

    # A radius far from any seeded city matches nothing.
    empty = client.post(
        "/api/v1/map/search", json={"radius": {"lat": 0.0, "lon": 0.0, "radius_km": 10.0}}
    ).json()
    assert empty["total_matched"] == 0


def test_search_by_polygon(client, milano_id):
    # Large box covering all of Milan's scattered demo listings.
    polygon = [
        [9.1900 - 0.1, 45.4642 - 0.1],
        [9.1900 - 0.1, 45.4642 + 0.1],
        [9.1900 + 0.1, 45.4642 + 0.1],
        [9.1900 + 0.1, 45.4642 - 0.1],
    ]
    response = client.post(
        "/api/v1/map/search", json={"area_id": milano_id, "polygon": polygon, "limit": 1000}
    )
    body = response.json()
    assert body["total_matched"] > 0

    # A tiny polygon far from Milan matches nothing.
    empty = client.post(
        "/api/v1/map/search",
        json={
            "polygon": [[0.0, 0.0], [0.0, 0.01], [0.01, 0.01], [0.01, 0.0]],
            "limit": 100,
        },
    ).json()
    assert empty["total_matched"] == 0
    assert empty["items"] == []


def test_polygon_requires_three_vertices(client):
    response = client.post(
        "/api/v1/map/search", json={"polygon": [[0.0, 0.0], [0.01, 0.01]]}
    )
    assert response.status_code == 422


def test_limit_truncates_results(client, milano_id):
    response = client.post(
        "/api/v1/map/search", json={"area_id": milano_id, "limit": 1}
    ).json()
    assert len(response["items"]) == 1
    assert response["total_matched"] >= 1
    if response["total_matched"] > 1:
        assert response["truncated"] is True


def test_price_and_property_type_filters_compose(client, milano_id):
    response = client.post(
        "/api/v1/map/search",
        json={
            "area_id": milano_id,
            "property_type": "penthouse",
            "max_price": 5_000_000,
            "limit": 500,
        },
    ).json()
    assert all(p["property_type"] == "penthouse" for p in response["items"])
    assert all(p["price"] <= 5_000_000 for p in response["items"])


def test_areas_geo_endpoint(client):
    response = client.get("/api/v1/map/areas-geo", params={"level": "neighborhood"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 9  # 3 cities x 3 neighborhoods in the demo config
    assert all("lat" in a and "lon" in a for a in body)
