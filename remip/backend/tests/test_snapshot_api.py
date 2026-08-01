"""End-to-end: creating/updating a listing stores a real snapshot on local
disk (test env has no S3 configured) and it's retrievable via the API."""


def test_listing_versions_have_snapshots(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    history = client.get(f"/api/v1/listings/{listing_id}/history").json()
    assert history
    assert all(v["has_snapshot"] for v in history)


def test_snapshot_content_matches_version(client, admin_headers):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    before = client.get(f"/api/v1/listings/{listing_id}").json()
    new_price = round(before["current_price"] * 0.85, -2)
    response = client.post(
        "/api/v1/admin/simulate/listing-update",
        json={"listing_id": listing_id, "changes": {"price": new_price}},
        headers=admin_headers,
    )
    version_number = response.json()["version"]["version_number"]

    snapshot = client.get(
        f"/api/v1/listings/{listing_id}/versions/{version_number}/snapshot"
    ).json()
    assert snapshot["storage_key"].startswith("file://")
    assert snapshot["content"]["price"] == new_price
    assert snapshot["content"]["version_number"] == version_number
    assert snapshot["content"]["listing_id"] == listing_id


def test_snapshot_not_found_for_unknown_version(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    response = client.get(f"/api/v1/listings/{listing_id}/versions/999/snapshot")
    assert response.status_code == 404
