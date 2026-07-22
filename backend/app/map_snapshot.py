from __future__ import annotations

from math import cos, floor, log2, radians
from urllib.parse import urlencode

from .models import MapSnapshotRequest

STATIC_MAPS_URL = "https://maps.googleapis.com/maps/api/staticmap"


def calculate_zoom(latitude: float, radius_km: float, viewport_height: int = 320) -> int:
    diameter_m = max(500.0, radius_km * 2_000 * 1.2)
    meters_per_pixel = diameter_m / viewport_height
    zoom = floor(log2(156543.03392 * max(0.15, cos(radians(latitude))) / meters_per_pixel))
    return max(2, min(19, zoom))


def build_static_map_url(payload: MapSnapshotRequest, api_key: str) -> str:
    center = f"{payload.center_latitude:.6f},{payload.center_longitude:.6f}"
    parameters: list[tuple[str, str]] = [
        ("center", center),
        ("zoom", str(calculate_zoom(payload.center_latitude, payload.radius_km))),
        ("size", "640x320"),
        ("scale", "2"),
        ("format", "png"),
        ("maptype", "roadmap"),
        ("language", "fr"),
        ("markers", f"size:mid|color:0x147da5|label:C|{center}"),
        ("style", "feature:water|color:0xdff4fb"),
        ("style", "feature:landscape|color:0xf1f7ed"),
        ("style", "feature:road|element:geometry|color:0xffffff"),
        ("style", "feature:poi|element:labels|visibility:simplified"),
    ]
    if payload.points:
        lead_locations = "|".join(f"{point.latitude:.6f},{point.longitude:.6f}" for point in payload.points)
        parameters.append(("markers", f"size:tiny|color:0xa8db47|{lead_locations}"))
    parameters.append(("key", api_key))
    return f"{STATIC_MAPS_URL}?{urlencode(parameters)}"

