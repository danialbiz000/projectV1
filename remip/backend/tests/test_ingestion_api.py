import pytest


@pytest.fixture(scope="module")
def milano_id(client):
    cities = client.get("/api/v1/geo/areas", params={"level": "city"}).json()
    return next(c["id"] for c in cities if c["name"] == "Milano")


def test_omi_quotations_endpoint(client, milano_id):
    response = client.get("/api/v1/market/omi-quotations", params={"area_id": milano_id})
    assert response.status_code == 200
    body = response.json()
    assert body["data"], "Milano should have OMI quotations from the seed bootstrap"
    row = body["data"][0]
    assert row["comune"] == "Milano"
    assert row["price_sqm_max"] >= row["price_sqm_min"]
    context = body["data_context"]
    assert context["sources"] == ["omi_it"]
    assert context["is_demo_data"] is True
    assert "fixture" in context["limitations"].lower() or "locale" in context["limitations"].lower()


def test_omi_quotations_unknown_area_404(client):
    response = client.get("/api/v1/market/omi-quotations", params={"area_id": "nope"})
    assert response.status_code == 404


def test_admin_ingestion_endpoints_require_admin(client, user_headers):
    assert client.get("/api/v1/admin/ingestion/jobs", headers=user_headers).status_code == 403
    assert (
        client.post("/api/v1/admin/ingestion/run/omi_it", headers=user_headers).status_code == 403
    )


def test_admin_can_list_ingestion_jobs(client, admin_headers):
    response = client.get("/api/v1/admin/ingestion/jobs", headers=admin_headers)
    assert response.status_code == 200
    jobs = response.json()
    assert jobs
    assert jobs[0]["provider_code"] == "omi_it"


def test_admin_trigger_ingestion_unknown_adapter_rejected(client, admin_headers):
    response = client.post("/api/v1/admin/ingestion/run/no-such-provider", headers=admin_headers)
    assert response.status_code == 400


def test_admin_trigger_ingestion_runs(client, admin_headers):
    response = client.post("/api/v1/admin/ingestion/run/omi_it", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] in ("queued", "inline")
    if body["mode"] == "inline":
        assert body["status"] == "success"
