class AddressGenerationInProgress(RuntimeError):
    """Une recherche est déjà en cours pour la même adresse normalisée."""


class InvalidMapSnapshotGrant(RuntimeError):
    """Le jeton de carte est absent, expiré ou déjà consommé."""


class MapSnapshotGrantInProgress(RuntimeError):
    """Le même jeton de carte est déjà en cours de consommation."""


class PlacesProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class StaticMapProviderError(RuntimeError):
    """Le fournisseur de carte n’a pas pu retourner une image valide."""


class EmptyExportError(ValueError):
    """Un export a été demandé sans aucune donnée."""
