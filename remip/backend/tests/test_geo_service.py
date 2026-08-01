from app.services.geo import circle_polygon, haversine_km, point_in_polygon


def test_haversine_known_distance():
    # Milan <-> Rome, ~477 km great-circle distance.
    milan = (45.4642, 9.1900)
    rome = (41.9028, 12.4964)
    dist = haversine_km(*milan, *rome)
    assert 470 < dist < 490


def test_haversine_zero_for_same_point():
    assert haversine_km(45.0, 9.0, 45.0, 9.0) == 0.0


def test_point_in_polygon_square():
    square = [(9.0, 45.0), (9.0, 45.1), (9.1, 45.1), (9.1, 45.0)]
    assert point_in_polygon(45.05, 9.05, square) is True
    assert point_in_polygon(46.0, 9.05, square) is False


def test_point_in_polygon_needs_three_vertices():
    assert point_in_polygon(45.0, 9.0, [(9.0, 45.0), (9.1, 45.1)]) is False


def test_circle_polygon_is_closed_ring_around_center():
    ring = circle_polygon(45.0, 9.0, radius_km=1.0, points=8)
    assert len(ring) == 9  # 8 points + closing point
    assert ring[0] == ring[-1]
    # every vertex should be roughly radius_km away from the center
    for lon, lat in ring[:-1]:
        assert 0.8 < haversine_km(45.0, 9.0, lat, lon) < 1.2
