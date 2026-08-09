from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID


class InvalidAuditEvent(ValueError):
    pass


class InvalidAuditMetadata(InvalidAuditEvent):
    pass


class AuditScope(StrEnum):
    TENANT = "tenant"
    PLATFORM = "platform"


class AuditActorKind(StrEnum):
    USER = "user"
    SYSTEM = "system"


class AuditSource(StrEnum):
    API = "api"
    CLI = "cli"
    WORKER = "worker"


class AuditAction(StrEnum):
    ORGANIZATION_UPDATED = "organization.updated"
    ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED = "account.organization_preference_changed"
    MEMBERSHIP_ROLE_CHANGED = "membership.role_changed"
    MEMBERSHIP_STATUS_CHANGED = "membership.status_changed"
    INVITATION_CREATED = "invitation.created"
    INVITATION_RESEND_REQUESTED = "invitation.resend_requested"
    INVITATION_DELIVERY_COMPLETED = "invitation.delivery_completed"
    INVITATION_REVOKED = "invitation.revoked"
    INVITATION_ACCEPTED = "invitation.accepted"
    ORGANIZATION_ACTIVATED = "organization.activated"
    ORGANIZATION_PROVISIONED = "organization.provisioned"
    INITIAL_INVITATION_CREATED = "organization.initial_invitation.created"
    INITIAL_INVITATION_RESEND_REQUESTED = "organization.initial_invitation.resend_requested"
    INITIAL_INVITATION_DELIVERY_COMPLETED = "organization.initial_invitation.delivery_completed"
    INITIAL_INVITATION_REVOKED = "organization.initial_invitation.revoked"
    ORGANIZATION_SUSPENDED = "organization.suspended"
    ORGANIZATION_REACTIVATED = "organization.reactivated"


_ENTITY_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$", re.ASCII)
_EXTERNAL_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}$", re.ASCII)
_ORGANIZATION_FIELDS = frozenset({"locale", "name", "timezone"})
_MEMBERSHIP_ROLES = frozenset({"admin", "manager", "sales"})
_MEMBERSHIP_STATUSES = frozenset({"active", "disabled"})
_INVITATION_KINDS = frozenset({"initial_administrator", "member"})
_DELIVERY_STATUSES = frozenset({"pending", "sent", "failed"})
_DELIVERY_KINDS = frozenset({"initial", "resend"})
_STATUS_REASON_CODES = frozenset({"administrative", "billing", "compliance", "customer_request", "other", "security"})
_TENANT_ACTIONS = frozenset(
    {
        AuditAction.ORGANIZATION_UPDATED,
        AuditAction.ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED,
        AuditAction.MEMBERSHIP_ROLE_CHANGED,
        AuditAction.MEMBERSHIP_STATUS_CHANGED,
        AuditAction.INVITATION_CREATED,
        AuditAction.INVITATION_RESEND_REQUESTED,
        AuditAction.INVITATION_DELIVERY_COMPLETED,
        AuditAction.INVITATION_REVOKED,
        AuditAction.INVITATION_ACCEPTED,
        AuditAction.ORGANIZATION_ACTIVATED,
    }
)
_PLATFORM_ACTIONS = frozenset(set(AuditAction) - _TENANT_ACTIONS)
_ACTION_ENTITY_TYPES = {
    AuditAction.ORGANIZATION_UPDATED: "organization",
    AuditAction.ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED: "user",
    AuditAction.MEMBERSHIP_ROLE_CHANGED: "membership",
    AuditAction.MEMBERSHIP_STATUS_CHANGED: "membership",
    AuditAction.INVITATION_CREATED: "invitation",
    AuditAction.INVITATION_RESEND_REQUESTED: "invitation",
    AuditAction.INVITATION_DELIVERY_COMPLETED: "invitation",
    AuditAction.INVITATION_REVOKED: "invitation",
    AuditAction.INVITATION_ACCEPTED: "invitation",
    AuditAction.ORGANIZATION_ACTIVATED: "organization",
    AuditAction.ORGANIZATION_PROVISIONED: "organization",
    AuditAction.INITIAL_INVITATION_CREATED: "invitation",
    AuditAction.INITIAL_INVITATION_RESEND_REQUESTED: "invitation",
    AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED: "invitation",
    AuditAction.INITIAL_INVITATION_REVOKED: "invitation",
    AuditAction.ORGANIZATION_SUSPENDED: "organization",
    AuditAction.ORGANIZATION_REACTIVATED: "organization",
}


def audit_actions_for_scope(scope: AuditScope) -> tuple[AuditAction, ...]:
    actions = _TENANT_ACTIONS if scope is AuditScope.TENANT else _PLATFORM_ACTIONS
    return tuple(sorted(actions, key=lambda action: action.value))


def audit_entity_types_for_scope(scope: AuditScope) -> tuple[str, ...]:
    return tuple(sorted({_ACTION_ENTITY_TYPES[action] for action in audit_actions_for_scope(scope)}))


def audit_entity_type_for_action(action: AuditAction) -> str:
    return _ACTION_ENTITY_TYPES[action]


def audit_action_matches_scope(action: AuditAction, scope: AuditScope) -> bool:
    return action in (_TENANT_ACTIONS if scope is AuditScope.TENANT else _PLATFORM_ACTIONS)


class AuditMetadataPolicy:
    """Valide et normalise les seules métadonnées permises pour une action stable."""

    @classmethod
    def validate(cls, action: AuditAction, metadata: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(metadata, Mapping):
            raise InvalidAuditMetadata("Les métadonnées d’audit doivent être un objet.")

        values = dict(metadata)
        if action is AuditAction.ORGANIZATION_UPDATED:
            cls._require_keys(values, {"changed_fields"})
            changed_fields = values["changed_fields"]
            if (
                isinstance(changed_fields, (str, bytes))
                or not isinstance(changed_fields, Sequence)
                or not changed_fields
                or any(
                    not isinstance(field_name, str) or field_name not in _ORGANIZATION_FIELDS
                    for field_name in changed_fields
                )
                or len(set(changed_fields)) != len(changed_fields)
            ):
                raise InvalidAuditMetadata("changed_fields contient une valeur interdite ou dupliquée.")
            return {"changed_fields": tuple(sorted(changed_fields))}

        if action is AuditAction.ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED:
            cls._require_keys(values, {"previous_membership_id", "new_membership_id"})
            return {
                "previous_membership_id": cls._uuid(values["previous_membership_id"], "previous_membership_id"),
                "new_membership_id": cls._uuid(values["new_membership_id"], "new_membership_id"),
            }

        if action is AuditAction.MEMBERSHIP_ROLE_CHANGED:
            cls._require_keys(values, {"previous_role", "new_role"})
            return {
                "previous_role": cls._choice(values["previous_role"], _MEMBERSHIP_ROLES, "previous_role"),
                "new_role": cls._choice(values["new_role"], _MEMBERSHIP_ROLES, "new_role"),
            }

        if action is AuditAction.MEMBERSHIP_STATUS_CHANGED:
            cls._require_keys(values, {"previous_status", "new_status"})
            return {
                "previous_status": cls._choice(values["previous_status"], _MEMBERSHIP_STATUSES, "previous_status"),
                "new_status": cls._choice(values["new_status"], _MEMBERSHIP_STATUSES, "new_status"),
            }

        if action in {AuditAction.INVITATION_CREATED, AuditAction.INITIAL_INVITATION_CREATED}:
            cls._require_keys(values, {"role", "invitation_kind", "delivery_status"})
            return {
                "role": cls._choice(values["role"], _MEMBERSHIP_ROLES, "role"),
                "invitation_kind": cls._choice(values["invitation_kind"], _INVITATION_KINDS, "invitation_kind"),
                "delivery_status": cls._choice(values["delivery_status"], _DELIVERY_STATUSES, "delivery_status"),
            }

        if action in {
            AuditAction.INVITATION_RESEND_REQUESTED,
            AuditAction.INITIAL_INVITATION_RESEND_REQUESTED,
        }:
            cls._require_keys(values, {"delivery_attempt_id"})
            return {"delivery_attempt_id": cls._uuid(values["delivery_attempt_id"], "delivery_attempt_id")}

        if action in {
            AuditAction.INVITATION_DELIVERY_COMPLETED,
            AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED,
        }:
            cls._require_keys(values, {"delivery_status", "delivery_kind", "delivery_attempt_id"})
            return {
                "delivery_status": cls._choice(values["delivery_status"], _DELIVERY_STATUSES, "delivery_status"),
                "delivery_kind": cls._choice(values["delivery_kind"], _DELIVERY_KINDS, "delivery_kind"),
                "delivery_attempt_id": cls._uuid(values["delivery_attempt_id"], "delivery_attempt_id"),
            }

        if action is AuditAction.ORGANIZATION_SUSPENDED:
            cls._require_keys(values, {"reason_code", "operation_id"}, {"external_reference"})
            result = cls._status_operation(values)
            external_reference = values.get("external_reference")
            if external_reference is not None:
                if not isinstance(external_reference, str) or not _EXTERNAL_REFERENCE_PATTERN.fullmatch(
                    external_reference
                ):
                    raise InvalidAuditMetadata("external_reference ne respecte pas le format autorisé.")
                result["external_reference"] = external_reference
            return result

        if action is AuditAction.ORGANIZATION_REACTIVATED:
            cls._require_keys(values, {"reason_code", "operation_id"})
            return cls._status_operation(values)

        cls._require_keys(values, set())
        return {}

    @staticmethod
    def _require_keys(
        values: Mapping[str, object],
        required: set[str],
        optional: set[str] | None = None,
    ) -> None:
        allowed = required | (optional or set())
        if set(values) != required and not (required <= set(values) <= allowed):
            raise InvalidAuditMetadata("Les clés de métadonnées ne correspondent pas à la politique de l’action.")

    @staticmethod
    def _uuid(value: object, field_name: str) -> str:
        if not isinstance(value, UUID):
            raise InvalidAuditMetadata(f"{field_name} doit être un UUID interne.")
        return str(value)

    @staticmethod
    def _choice(value: object, choices: frozenset[str], field_name: str) -> str:
        if not isinstance(value, str) or value not in choices:
            raise InvalidAuditMetadata(f"{field_name} contient un code non autorisé.")
        return value

    @classmethod
    def _status_operation(cls, values: Mapping[str, object]) -> dict[str, object]:
        return {
            "reason_code": cls._choice(values["reason_code"], _STATUS_REASON_CODES, "reason_code"),
            "operation_id": cls._uuid(values["operation_id"], "operation_id"),
        }


@dataclass(frozen=True, slots=True)
class AuditEventDraft:
    id: UUID
    scope: AuditScope
    action: AuditAction
    entity_type: str
    entity_id: UUID | None
    actor_kind: AuditActorKind
    actor_id: UUID | None
    organization_id: UUID | None
    request_id: str
    correlation_id: str
    source: AuditSource
    metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.scope, AuditScope):
            raise InvalidAuditEvent("La portée d’audit est invalide.")
        if not isinstance(self.action, AuditAction):
            raise InvalidAuditEvent("Le code d’action d’audit est inconnu.")
        if not isinstance(self.actor_kind, AuditActorKind):
            raise InvalidAuditEvent("Le type d’acteur d’audit est invalide.")
        if not isinstance(self.source, AuditSource):
            raise InvalidAuditEvent("La source d’audit est invalide.")
        if self.scope is AuditScope.TENANT and self.organization_id is None:
            raise InvalidAuditEvent("Une organisation est obligatoire pour un événement locataire.")
        if (self.scope is AuditScope.TENANT and self.action not in _TENANT_ACTIONS) or (
            self.scope is AuditScope.PLATFORM and self.action not in _PLATFORM_ACTIONS
        ):
            raise InvalidAuditEvent("L’action d’audit n’est pas autorisée dans cette portée.")
        if self.actor_kind is AuditActorKind.USER and self.actor_id is None:
            raise InvalidAuditEvent("Un identifiant d’acteur est obligatoire pour un acteur utilisateur.")
        if self.actor_kind is AuditActorKind.SYSTEM and self.actor_id is not None:
            raise InvalidAuditEvent("Un événement système ne porte pas d’identifiant utilisateur.")
        if not _ENTITY_TYPE_PATTERN.fullmatch(self.entity_type):
            raise InvalidAuditEvent("Le type d’entité d’audit est invalide.")
        if self.entity_type != _ACTION_ENTITY_TYPES[self.action]:
            raise InvalidAuditEvent("Le type d’entité ne correspond pas à l’action d’audit.")
        _validate_context_identifier(self.request_id, "request_id")
        _validate_context_identifier(self.correlation_id, "correlation_id")
        if self.schema_version <= 0:
            raise InvalidAuditEvent("schema_version doit être strictement positif.")
        normalized = AuditMetadataPolicy.validate(self.action, self.metadata)
        serialized_metadata = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
        if len(serialized_metadata.encode("utf-8")) > 8192:
            raise InvalidAuditMetadata("Les métadonnées d’audit dépassent 8 Kio.")
        object.__setattr__(self, "metadata", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class AuditEventFilter:
    occurred_from: datetime
    occurred_to: datetime
    action: AuditAction | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuditActorView:
    kind: AuditActorKind
    id: UUID | None
    display_name: str | None


@dataclass(frozen=True, slots=True)
class AuditEventView:
    id: UUID
    occurred_at: datetime
    action: str
    entity_type: str
    entity_id: UUID | None
    actor: AuditActorView
    request_id: str
    correlation_id: str
    source: AuditSource
    metadata: Mapping[str, object]
    schema_version: int


def _validate_context_identifier(value: str, field_name: str) -> None:
    if not 1 <= len(value) <= 128 or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise InvalidAuditEvent(f"{field_name} doit contenir entre 1 et 128 caractères sans contrôle.")
