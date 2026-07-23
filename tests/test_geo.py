from backend.app.geo import haversine_km


def test_haversine_is_zero_for_same_point():
    assert haversine_km(46.8139, -71.2080, 46.8139, -71.2080) == 0
