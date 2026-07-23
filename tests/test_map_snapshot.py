from urllib.parse import parse_qs, urlparse

from backend.app.map_snapshot import build_static_map_url, calculate_zoom
from backend.app.models import MapPoint, MapSnapshotRequest


def test_zoom_decreases_when_radius_increases() -> None:
    close_zoom = calculate_zoom(46.8139, 2)
    wide_zoom = calculate_zoom(46.8139, 40)

    assert 2 <= wide_zoom < close_zoom <= 19


def test_static_map_url_contains_center_and_place_markers() -> None:
    payload = MapSnapshotRequest(
        center_latitude=46.8139,
        center_longitude=-71.2080,
        radius_km=12,
        points=[MapPoint(latitude=46.82, longitude=-71.21)],
    )

    parsed = urlparse(build_static_map_url(payload, "test-static-key"))
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "maps.googleapis.com"
    assert parsed.path == "/maps/api/staticmap"
    assert query["center"] == ["46.813900,-71.208000"]
    assert query["size"] == ["640x320"]
    assert query["scale"] == ["2"]
    assert query["key"] == ["test-static-key"]
    assert len(query["markers"]) == 2
    assert "label:C" in query["markers"][0]
    assert "46.820000,-71.210000" in query["markers"][1]
