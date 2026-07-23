"""Façade de compatibilité des fonctions géographiques encore actives."""

from .domain.geo import EARTH_RADIUS_KM, haversine_km

__all__ = ["EARTH_RADIUS_KM", "haversine_km"]
