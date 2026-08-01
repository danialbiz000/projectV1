def test_create_valuation_requires_auth(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    response = client.post(f"/api/v1/listings/{listing_id}/valuations")
    assert response.status_code == 401


def test_create_and_list_valuation(client, user_headers):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    detail = client.get(f"/api/v1/listings/{listing_id}").json()

    response = client.post(f"/api/v1/listings/{listing_id}/valuations", headers=user_headers)
    if detail["estimate"] is None:
        assert response.status_code == 422
        return

    assert response.status_code == 201
    body = response.json()
    assert body["listing_id"] == listing_id
    assert body["range_low"] <= body["estimated_value"] <= body["range_high"]
    assert 0 < body["confidence"] <= 1
    assert body["n_comparables"] >= 3

    history = client.get(f"/api/v1/listings/{listing_id}/valuations").json()
    assert len(history) >= 1
    assert history[0]["id"] == body["id"]

    # a second snapshot is a genuinely new row, not an update-in-place
    second = client.post(f"/api/v1/listings/{listing_id}/valuations", headers=user_headers)
    assert second.status_code == 201
    history_after = client.get(f"/api/v1/listings/{listing_id}/valuations").json()
    assert len(history_after) == len(history) + 1
    assert history_after[0]["id"] == second.json()["id"]  # most recent first


def test_valuation_unknown_listing_404(client, user_headers):
    assert client.post("/api/v1/listings/nope/valuations", headers=user_headers).status_code == 404
    assert client.get("/api/v1/listings/nope/valuations").status_code == 404


def test_find_a_listing_with_enough_comparables_and_valuate(client, user_headers):
    """Sweeps a page of listings to find one with >=3 comparables (some demo
    property types are sparse per area) so the success path is genuinely
    exercised regardless of dataset composition."""
    listings = client.get("/api/v1/listings", params={"limit": 100}).json()["items"]
    for item in listings:
        detail = client.get(f"/api/v1/listings/{item['id']}").json()
        if detail["estimate"] is not None:
            response = client.post(
                f"/api/v1/listings/{item['id']}/valuations", headers=user_headers
            )
            assert response.status_code == 201
            return
    raise AssertionError("expected at least one demo listing with >=3 comparables")
