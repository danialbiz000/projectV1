from tests.conftest import login


def _register_and_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    return login(client, email, "password123")


def test_default_preferences(client):
    headers = _register_and_login(client, "prefs.default@example.com")
    body = client.get("/api/v1/notifications/preferences", headers=headers).json()
    assert body == {"frequency": "instant", "muted_types": [], "updated_at": None}


def test_update_preferences_requires_auth(client):
    assert client.get("/api/v1/notifications/preferences").status_code == 401
    assert client.put("/api/v1/notifications/preferences", json={}).status_code == 401


def test_update_preferences_rejects_unknown_type(client):
    headers = _register_and_login(client, "prefs.invalid@example.com")
    response = client.put(
        "/api/v1/notifications/preferences",
        json={"frequency": "instant", "muted_types": ["not_a_real_type"]},
        headers=headers,
    )
    assert response.status_code == 400


def test_update_preferences_persists(client):
    headers = _register_and_login(client, "prefs.persist@example.com")
    response = client.put(
        "/api/v1/notifications/preferences",
        json={"frequency": "daily_digest", "muted_types": ["price_increase"]},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["frequency"] == "daily_digest"
    assert body["muted_types"] == ["price_increase"]
    assert body["updated_at"] is not None

    refetched = client.get("/api/v1/notifications/preferences", headers=headers).json()
    assert refetched["frequency"] == "daily_digest"
    assert refetched["muted_types"] == ["price_increase"]


def test_muted_type_suppresses_notification(client, admin_headers):
    headers = _register_and_login(client, "prefs.mute@example.com")

    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    watchlist = client.get("/api/v1/watchlists", headers=headers).json()[0]
    client.post(
        f"/api/v1/watchlists/{watchlist['id']}/items",
        json={"kind": "listing", "listing_id": listing_id},
        headers=headers,
    )
    client.put(
        "/api/v1/notifications/preferences",
        json={"frequency": "instant", "muted_types": ["price_drop"]},
        headers=headers,
    )

    before = client.get(f"/api/v1/listings/{listing_id}").json()
    client.post(
        "/api/v1/admin/simulate/listing-update",
        json={
            "listing_id": listing_id,
            "changes": {"price": round(before["current_price"] * 0.9)},
        },
        headers=admin_headers,
    )

    notifications = client.get("/api/v1/notifications", headers=headers).json()
    assert all(n["type"] != "price_drop" for n in notifications["items"])
