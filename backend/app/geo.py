from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class SearchTile:
    index: int
    latitude: float
    longitude: float
    bias_radius_m: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def destination_point(latitude: float, longitude: float, distance_km: float, bearing_deg: float) -> tuple[float, float]:
    angular = distance_km / EARTH_RADIUS_KM
    bearing = radians(bearing_deg)
    lat1 = radians(latitude)
    lon1 = radians(longitude)
    lat2 = asin(sin(lat1) * cos(angular) + cos(lat1) * sin(angular) * cos(bearing))
    lon2 = lon1 + atan2(sin(bearing) * sin(angular) * cos(lat1), cos(angular) - sin(lat1) * sin(lat2))
    return degrees(lat2), ((degrees(lon2) + 540) % 360) - 180


def generate_tiles(latitude: float, longitude: float, radius_km: float, max_tiles: int) -> list[SearchTile]:
    """Distribute location biases with a deterministic sunflower pattern."""
    bias_radius_m = min(50_000.0, max(500.0, radius_km * 1000 * 1.35 / sqrt(max_tiles)))
    tiles = [SearchTile(1, latitude, longitude, bias_radius_m)]
    if max_tiles == 1:
        return tiles

    golden_angle = 137.507764
    for offset in range(1, max_tiles):
        fraction = sqrt(offset / (max_tiles - 1))
        distance_km = radius_km * 0.78 * fraction
        tile_lat, tile_lon = destination_point(latitude, longitude, distance_km, offset * golden_angle)
        tiles.append(SearchTile(offset + 1, tile_lat, tile_lon, bias_radius_m))
    return tiles

