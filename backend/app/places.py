"""Façade de compatibilité du client Google Places historique."""

from .infrastructure.google.places import (
    BASE_FIELDS,
    CONTACT_FIELDS,
    PLACES_URL,
    GooglePlacesClient,
    GooglePlacesError,
    GooglePlacesSettings,
    PlacesPage,
)

__all__ = [
    "BASE_FIELDS",
    "CONTACT_FIELDS",
    "PLACES_URL",
    "GooglePlacesClient",
    "GooglePlacesError",
    "GooglePlacesSettings",
    "PlacesPage",
]
