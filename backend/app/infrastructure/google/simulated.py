"""Fournisseur Google déterministe, réservé aux recettes locales.

Il ne crée aucune requête HTTP et ne retient aucun critère de recherche. Les
résultats sont synthétiques et sans coordonnées afin de pouvoir tester le
parcours de quota et d'usage sans conserver de donnée de localisation externe.
"""

from __future__ import annotations

from ...application.models import GooglePlaceSearchCriteria
from ...application.ports.places import PlaceCandidate


class SimulatedGooglePlacesGateway:
    """Retourne un petit jeu immuable de résultats de recette."""

    async def search(self, criteria: GooglePlaceSearchCriteria) -> list[PlaceCandidate]:
        del criteria
        return [
            PlaceCandidate(
                place_id="e2e06-simulated-place-01",
                name="Atelier simulé Alpha",
                address="Adresse synthétique — recette E2E-06",
                primary_type="plumber",
                business_status="OPERATIONAL",
                service_area_business=True,
            ),
            PlaceCandidate(
                place_id="e2e06-simulated-place-02",
                name="Atelier simulé Beta",
                address="Adresse synthétique — recette E2E-06",
                primary_type="plumber",
                business_status="OPERATIONAL",
                service_area_business=True,
            ),
        ]
