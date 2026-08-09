class GoogleSearchInProgress(RuntimeError):
    """Une recherche Google est déjà en cours pour le même acteur locataire."""


class InvalidMapSnapshotGrant(RuntimeError):
    """Le jeton de carte est absent, expiré ou déjà consommé."""


class MapSnapshotGrantInProgress(RuntimeError):
    """Le même jeton de carte est déjà en cours de consommation."""


class MapSnapshotGrantCapacityReached(RuntimeError):
    """Le stockage éphémère ne peut pas émettre une nouvelle concession."""


class ActiveOrganizationRequired(RuntimeError):
    """Une organisation active est obligatoire pour l’opération locataire."""


class JsonContentTypeRequired(RuntimeError):
    """La commande HTTP doit utiliser le type application/json."""


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


class OrganizationAdministrationUnavailable(RuntimeError):
    """Le stockage d’administration locataire est temporairement indisponible."""


class OrganizationResourceNotFound(RuntimeError):
    """La ressource n’existe pas dans l’organisation active."""


class OrganizationVersionConflict(RuntimeError):
    def __init__(self, current_version: int | None = None) -> None:
        super().__init__("L’organisation a été modifiée depuis sa lecture.")
        self.current_version = current_version


class MembershipVersionConflict(RuntimeError):
    def __init__(self, current_version: int | None = None) -> None:
        super().__init__("L’appartenance a été modifiée depuis sa lecture.")
        self.current_version = current_version


class LastActiveAdministrator(RuntimeError):
    """La modification supprimerait le dernier Administrateur actif."""


class MembershipAlreadyActive(RuntimeError):
    """Le destinataire possède déjà une appartenance active."""


class InvitationAlreadyPending(RuntimeError):
    """Une invitation non terminale existe déjà pour ce destinataire."""


class OrganizationNotActive(RuntimeError):
    """L’organisation n’est pas active pour cette opération."""


class OrganizationSwitchForbidden(RuntimeError):
    """L’appartenance ou l’organisation ne permet pas le changement demandé."""


class SessionRotationFailed(RuntimeError):
    """La session courante n’a pas pu être renouvelée sans ambiguïté."""


class AuditUnavailable(RuntimeError):
    """Le journal d’audit ne peut pas être consulté actuellement."""


class InvalidAuditCursor(ValueError):
    """Le curseur d’audit ne correspond pas à la requête courante."""
