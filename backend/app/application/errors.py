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


class PlatformAdministratorNotFound(RuntimeError):
    """Le compte ciblé n’est pas un administrateur de plateforme connu."""


class IdentityConcurrentUpdate(RuntimeError):
    """L’identité a changé depuis sa lecture dans la transaction."""


class InsufficientCapability(RuntimeError):
    """L’acteur authentifié ne possède pas la capacité demandée."""


class ProvisioningServiceUnavailable(RuntimeError):
    """Le stockage nécessaire au provisioning est indisponible."""


class InvitationDeliveryUnavailable(RuntimeError):
    """Aucun transport d’invitation autorisé n’est configuré."""


class InvitationDeliveryFailed(RuntimeError):
    """Le transport configuré n’a pas accepté le message."""


class ProvisioningOutcomeUnknown(RuntimeError):
    """La transaction principale a réussi mais sa finalisation est inconnue."""


class IdempotencyKeyReused(RuntimeError):
    """Une clé d’idempotence a été réutilisée avec une autre commande."""


class ProvisioningResourceNotFound(RuntimeError):
    """La ressource de provisioning n’existe pas ou n’est plus modifiable."""


class InvitationInvalid(RuntimeError):
    """Le jeton ne correspond pas à une invitation utilisable."""


class InvitationAuthenticationRequired(RuntimeError):
    """Le compte invité existant doit être authentifié."""


class InvitationAccountMismatch(RuntimeError):
    """La session active n’appartient pas au destinataire invité."""


class InvitationAlreadyAccepted(RuntimeError):
    """Une invitation acceptée ne peut plus être révoquée."""


class MembershipReactivationRequired(RuntimeError):
    """Une appartenance désactivée doit être réactivée explicitement."""


class SessionConflict(RuntimeError):
    """Une autre session doit être fermée avant la création du compte invité."""


class InvitationRateLimited(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Trop de tentatives d’invitation.")
        self.retry_after_seconds = max(1, retry_after_seconds)


class SessionCreationFailedAfterAcceptance(RuntimeError):
    """L’invitation est acceptée, mais la nouvelle session n’a pas pu être créée."""
