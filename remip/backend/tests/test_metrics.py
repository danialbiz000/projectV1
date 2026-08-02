"""GET /metrics (M6) — Prometheus-format request counters, see
app/core/metrics.py and the observability middleware in app/main.py."""
from app.core.metrics import reset


def test_metrics_endpoint_reports_requests(client):
    reset()
    client.get("/health")
    client.get("/health")

    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert 'remip_http_requests_total{method="GET",path="/health",status="200"} 2' in body
    assert "remip_http_request_duration_seconds_sum" in body
    assert "remip_process_uptime_seconds" in body


def test_metrics_uses_the_route_template_not_the_raw_path(client):
    reset()
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    client.get(f"/api/v1/listings/{listing_id}")

    body = client.get("/metrics").text
    assert "/listings/{listing_id}" in body
    assert listing_id not in body
