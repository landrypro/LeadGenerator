from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Contexte d’acteur global créé côté serveur, sans portée locataire."""

    actor_id: UUID
    request_id: str

    def __post_init__(self) -> None:
        _validate_request_id(self.request_id)


@dataclass(frozen=True, slots=True)
class InvitationAcceptanceContext:
    """Contexte serveur d’une acceptation, avant établissement éventuel du locataire."""

    request_id: str
    actor_id: UUID | None = None

    def __post_init__(self) -> None:
        _validate_request_id(self.request_id)


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Contexte locataire créé côté serveur pour une transaction PostgreSQL."""

    actor_id: UUID
    organization_id: UUID
    request_id: str

    def __post_init__(self) -> None:
        _validate_request_id(self.request_id)


def _validate_request_id(request_id: str) -> None:
    if not 1 <= len(request_id) <= 128:
        raise ValueError("request_id doit contenir entre 1 et 128 caractères.")
    if any(ord(character) < 32 or ord(character) == 127 for character in request_id):
        raise ValueError("request_id ne doit contenir aucun caractère de contrôle.")
