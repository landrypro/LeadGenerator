"""Façade de compatibilité de la génération d’URL Maps Static."""

from .infrastructure.google.static_maps import STATIC_MAPS_URL, build_static_map_url, calculate_zoom

__all__ = ["STATIC_MAPS_URL", "build_static_map_url", "calculate_zoom"]
