"""Security: users must never see other users' watchlists or notifications."""
from tests.conftest import login


def _register_and_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    return login(client, email, "password123")


def test_watchlist_isolation(client):
    headers_a = _register_and_login(client, "alice.isolation@example.com")
    headers_b = _register_and_login(client, "bob.isolation@example.com")

    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    watchlist_a = client.get("/api/v1/watchlists", headers=headers_a).json()[0]
    response = client.post(
        f"/api/v1/watchlists/{watchlist_a['id']}/items",
        json={"kind": "listing", "listing_id": listing_id},
        headers=headers_a,
    )
    assert response.status_code == 201
    assert response.json()["initial_price"] is not None

    # B only sees their own (empty) watchlist
    watchlists_b = client.get("/api/v1/watchlists", headers=headers_b).json()
    assert all(w["id"] != watchlist_a["id"] for w in watchlists_b)
    assert all(not w["items"] for w in watchlists_b)

    # B cannot write into A's watchlist (404: existence not leaked)
    response = client.post(
        f"/api/v1/watchlists/{watchlist_a['id']}/items",
        json={"kind": "listing", "listing_id": listing_id},
        headers=headers_b,
    )
    assert response.status_code == 404


def test_notification_isolation(client, user_headers):
    headers_c = _register_and_login(client, "carol.isolation@example.com")
    assert client.get("/api/v1/notifications", headers=headers_c).json()["total"] == 0

    demo_notifications = client.get("/api/v1/notifications", headers=user_headers).json()
    if demo_notifications["items"]:
        foreign_id = demo_notifications["items"][0]["id"]
        response = client.post(f"/api/v1/notifications/{foreign_id}/read", headers=headers_c)
        assert response.status_code == 404


def test_watchlist_area_items(client):
    headers = _register_and_login(client, "dave.area@example.com")
    area_id = client.get("/api/v1/geo/areas", params={"level": "city"}).json()[0]["id"]
    watchlist = client.get("/api/v1/watchlists", headers=headers).json()[0]
    response = client.post(
        f"/api/v1/watchlists/{watchlist['id']}/items",
        json={"kind": "area", "area_id": area_id, "thresholds": {"price_change_pct": 2}},
        headers=headers,
    )
    assert response.status_code == 201
    response = client.post(
        f"/api/v1/watchlists/{watchlist['id']}/items",
        json={"kind": "listing"},
        headers=headers,
    )
    assert response.status_code == 400
