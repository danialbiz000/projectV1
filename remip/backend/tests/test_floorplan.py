"""Illustrative floor plan generation (M7) — services/floorplan.py and
GET /listings/{id}/floorplan."""
import pytest

from app.services.floorplan import CANVAS_HEIGHT, CANVAS_WIDTH, generate_floorplan


@pytest.mark.parametrize(
    ("rooms", "bathrooms", "size_sqm", "property_type"),
    [
        (3, 1, 80.0, "apartment"),
        (1, 1, 35.0, "studio"),
        (5, 2, 150.0, "detached_house"),
        (2, 2, 60.0, "apartment"),
        (1, 1, 20.0, "apartment"),  # tiny unit with many nominal "rooms" edge case
    ],
)
def test_room_areas_sum_to_total_size(rooms, bathrooms, size_sqm, property_type):
    plan = generate_floorplan(rooms, bathrooms, size_sqm, property_type)
    assert sum(r["area_sqm"] for r in plan["rooms"]) == pytest.approx(size_sqm, abs=0.5)


def test_rectangles_stay_within_canvas_bounds():
    plan = generate_floorplan(4, 2, 100.0, "apartment")
    for room in plan["rooms"]:
        assert room["x"] >= 0
        assert room["y"] >= 0
        assert room["x"] + room["width"] <= CANVAS_WIDTH + 0.01
        assert room["y"] + room["height"] <= CANVAS_HEIGHT + 0.01
        assert room["width"] > 0
        assert room["height"] > 0


def test_studio_has_combined_main_room_and_no_bedrooms():
    plan = generate_floorplan(1, 1, 35.0, "studio")
    labels = [r["label"] for r in plan["rooms"]]
    assert "Soggiorno + Cucina" in labels
    assert not any("Camera" in label for label in labels)


def test_multi_room_apartment_has_living_room_kitchen_and_bedrooms():
    plan = generate_floorplan(3, 1, 80.0, "apartment")
    labels = [r["label"] for r in plan["rooms"]]
    assert "Soggiorno" in labels
    assert "Cucina" in labels
    assert sum(1 for label in labels if label.startswith("Camera")) == 2  # rooms - 1


def test_single_bedroom_is_not_numbered():
    plan = generate_floorplan(2, 1, 60.0, "apartment")
    labels = [r["label"] for r in plan["rooms"]]
    assert "Camera" in labels
    assert "Camera 1" not in labels


def test_multiple_bathrooms_are_numbered():
    plan = generate_floorplan(4, 2, 100.0, "apartment")
    labels = [r["label"] for r in plan["rooms"]]
    assert "Bagno 1" in labels and "Bagno 2" in labels


def test_generation_is_deterministic():
    first = generate_floorplan(3, 1, 80.0, "apartment")
    second = generate_floorplan(3, 1, 80.0, "apartment")
    assert first == second


def test_zero_bathrooms_still_gets_at_least_one():
    plan = generate_floorplan(3, 0, 80.0, "apartment")
    labels = [r["label"] for r in plan["rooms"]]
    assert "Bagno" in labels


def test_floorplan_endpoint(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["items"][0]["id"]
    response = client.get(f"/api/v1/listings/{listing_id}/floorplan")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["rooms"]
    assert body["data_context"]["is_demo_data"] is True
    assert "non deriva da alcuna planimetria reale" in body["data_context"]["methodology"]


def test_floorplan_endpoint_unknown_listing_404(client):
    response = client.get("/api/v1/listings/nope/floorplan")
    assert response.status_code == 404
