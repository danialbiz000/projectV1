def _watched_listing_id(client, user_headers) -> str:
    watchlists = client.get("/api/v1/watchlists", headers=user_headers).json()
    items = [item for w in watchlists for item in w["items"] if item["kind"] == "listing"]
    assert items, "demo seed should include a watched listing"
    return items[0]["listing_id"]


def test_simulated_price_drop_creates_version_and_notification(
    client, user_headers, admin_headers
):
    listing_id = _watched_listing_id(client, user_headers)
    before = client.get(f"/api/v1/listings/{listing_id}").json()
    new_price = round(before["current_price"] * 0.9)

    response = client.post(
        "/api/v1/admin/simulate/listing-update",
        json={"listing_id": listing_id, "changes": {"price": new_price}},
        headers=admin_headers,
    )
    assert response.status_code == 200
    version = response.json()["version"]
    assert version["diff"]["price"]["new"] == new_price

    after = client.get(f"/api/v1/listings/{listing_id}").json()
    assert after["current_price"] == new_price
    assert len(after["versions"]) == len(before["versions"]) + 1
    assert len(after["price_history"]) == len(before["price_history"]) + 1

    notifications = client.get("/api/v1/notifications", headers=user_headers).json()
    drops = [n for n in notifications["items"] if n["type"] == "price_drop"]
    assert drops, "watcher should be notified of the price drop"
    assert drops[0]["payload"]["listing_id"] == listing_id

    # idempotence: same price again is a no-op, no duplicate notification
    response = client.post(
        "/api/v1/admin/simulate/listing-update",
        json={"listing_id": listing_id, "changes": {"price": new_price}},
        headers=admin_headers,
    )
    assert response.json()["version"] is None
    again = client.get("/api/v1/notifications", headers=user_headers).json()
    assert len([n for n in again["items"] if n["type"] == "price_drop"]) == len(drops)


def test_removal_and_relisting_events(client, user_headers, admin_headers):
    listing_id = _watched_listing_id(client, user_headers)
    for changes, expected_type in [
        ({"status": "removed"}, "listing_removed"),
        ({"status": "relisted"}, "listing_relisted"),
    ]:
        response = client.post(
            "/api/v1/admin/simulate/listing-update",
            json={"listing_id": listing_id, "changes": changes},
            headers=admin_headers,
        )
        assert response.status_code == 200
        notifications = client.get("/api/v1/notifications", headers=user_headers).json()
        assert any(n["type"] == expected_type for n in notifications["items"])


def test_unversionable_field_rejected(client, admin_headers, user_headers):
    listing_id = _watched_listing_id(client, user_headers)
    response = client.post(
        "/api/v1/admin/simulate/listing-update",
        json={"listing_id": listing_id, "changes": {"id": "evil"}},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_simulate_requires_admin(client, user_headers):
    response = client.post(
        "/api/v1/admin/simulate/listing-update",
        json={"listing_id": "x", "changes": {"price": 1}},
        headers=user_headers,
    )
    assert response.status_code == 403


def test_mark_notifications_read(client, user_headers):
    listing = client.get("/api/v1/notifications", headers=user_headers).json()
    assert listing["unread"] > 0
    first = listing["items"][0]
    response = client.post(f"/api/v1/notifications/{first['id']}/read", headers=user_headers)
    assert response.json()["is_read"] is True
    client.post("/api/v1/notifications/read-all", headers=user_headers)
    assert client.get("/api/v1/notifications", headers=user_headers).json()["unread"] == 0
