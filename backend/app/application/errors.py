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


class InvalidCredentials(RuntimeError):
    """Les informations de connexion ne correspondent pas à un compte actif."""


class AuthenticationRequired(RuntimeError):
    """Une session valide est obligatoire."""


class CsrfValidationFailed(RuntimeError):
    """Le jeton ou l’origine CSRF est invalide."""


class AuthenticationServiceUnavailable(RuntimeError):
    """Une dépendance de sécurité ne permet pas d’authentifier la requête."""


class LoginRateLimited(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Trop de tentatives de connexion.")
        self.retry_after_seconds = max(1, retry_after_seconds)


class PlatformAdministratorAlreadyExists(RuntimeError):
    """Le bootstrap initial a déjà été exécuté."""
