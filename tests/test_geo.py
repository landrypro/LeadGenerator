from backend.app.geo import generate_tiles, haversine_km


def test_haversine_is_zero_for_same_point():
    assert haversine_km(46.8139, -71.2080, 46.8139, -71.2080) == 0


def test_tile_planner_returns_requested_count_and_center_first():
    tiles = generate_tiles(46.8139, -71.2080, 15, 8)

    assert len(tiles) == 8
    assert tiles[0].latitude == 46.8139
    assert tiles[0].longitude == -71.2080
    assert all(0 < tile.bias_radius_m <= 50_000 for tile in tiles)
