def test_countries_config(client):
    response = client.get("/api/v1/geo/countries")
    assert response.status_code == 200
    italy = next(c for c in response.json() if c["code"] == "IT")
    assert italy["currency"] == "EUR"
    assert italy["admin_levels"] == ["region", "province", "city", "neighborhood"]


def test_area_hierarchy(client):
    cities = client.get("/api/v1/geo/areas", params={"level": "city"}).json()
    assert {c["name"] for c in cities} == {"Milano", "Roma", "Bologna"}
    milano = next(c for c in cities if c["name"] == "Milano")
    neighborhoods = client.get(
        "/api/v1/geo/areas", params={"level": "neighborhood", "parent_id": milano["id"]}
    ).json()
    assert {n["name"] for n in neighborhoods} == {"Isola", "Navigli", "Città Studi", "Bicocca"}


def test_search_filters_and_pagination(client):
    cities = client.get("/api/v1/geo/areas", params={"level": "city"}).json()
    milano_id = next(c["id"] for c in cities if c["name"] == "Milano")

    # city-level search includes listings from child neighborhoods
    result = client.get(
        "/api/v1/listings", params={"area_id": milano_id, "limit": 100}
    ).json()
    assert result["total"] > 0
    assert all(item["status"] == "active" for item in result["items"])
    assert all(item["is_demo_data"] for item in result["items"])

    filtered = client.get(
        "/api/v1/listings",
        params={
            "area_id": milano_id,
            "max_price": 400000,
            "min_rooms": 2,
            "sort_by": "price",
            "sort_dir": "asc",
            "limit": 100,
        },
    ).json()
    prices = [item["current_price"] for item in filtered["items"]]
    assert prices == sorted(prices)
    assert all(p <= 400000 for p in prices)
    assert all(item["rooms"] >= 2 for item in filtered["items"])

    page = client.get("/api/v1/listings", params={"limit": 5, "offset": 0}).json()
    assert len(page["items"]) == 5
    assert page["total"] > 5


def test_invalid_sort_rejected(client):
    response = client.get("/api/v1/listings", params={"sort_by": "hackerman"})
    assert response.status_code == 400


def test_listing_detail(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    detail = client.get(f"/api/v1/listings/{listing_id}").json()
    assert detail["source_code"] == "demo_it"
    assert detail["is_demo_data"] is True
    assert detail["versions"][0]["version_number"] == 1
    assert len(detail["price_history"]) >= 1
    assert detail["price_per_sqm"] is not None
    # estimate, when present, is a range, never a single certain value
    if detail["estimate"]:
        est = detail["estimate"]
        assert est["range_low"] <= est["estimated_value"] <= est["range_high"]
        assert 0 < est["confidence"] <= 0.7
        assert "assumptions" in est


def test_listing_not_found(client):
    assert client.get("/api/v1/listings/non-esiste").status_code == 404


def test_sources_transparency(client):
    sources = client.get("/api/v1/sources").json()
    demo = next(s for s in sources if s["code"] == "demo_it")
    assert demo["is_demo"] is True and demo["enabled"] is True
    portal = next(s for s in sources if s["code"] == "portal_generic")
    assert portal["enabled"] is False and portal["tos_compliant"] is False
