from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .identity import MembershipRole, MembershipStatus, NormalizedEmail, normalize_email
from .provisioning import SUPPORTED_LOCALES, InvitationDeliveryStatus, InvitationState


class OrganizationStatusReasonCode(StrEnum):
    CUSTOMER_REQUEST = "customer_request"
    BILLING = "billing"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    ADMINISTRATIVE = "administrative"
    OTHER = "other"


_EXTERNAL_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}$", re.ASCII)


@dataclass(frozen=True, slots=True)
class OrganizationView:
    id: UUID
    name: str
    locale: str
    timezone: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MemberView:
    membership_id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: MembershipRole
    status: MembershipStatus
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MemberInvitationView:
    id: UUID
    recipient_email: str
    role: MembershipRole
    state: InvitationState
    delivery_status: InvitationDeliveryStatus
    expires_at: datetime
    created_at: datetime
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class UpdateOrganizationCommand:
    version: int
    name: str | None = None
    locale: str | None = None
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedUpdateOrganization:
    version: int
    name: str | None
    locale: str | None
    timezone: str | None


@dataclass(frozen=True, slots=True)
class UpdateMembershipCommand:
    version: int
    role: MembershipRole | None = None
    status: MembershipStatus | None = None


@dataclass(frozen=True, slots=True)
class CreateMemberInvitationCommand:
    email: str
    role: MembershipRole
    invitation_request_id: UUID


@dataclass(frozen=True, slots=True)
class ChangeOrganizationStatusCommand:
    operation_id: UUID
    version: int
    reason_code: OrganizationStatusReasonCode
    external_reference: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedChangeOrganizationStatus:
    operation_id: UUID
    version: int
    reason_code: OrganizationStatusReasonCode
    external_reference: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ValidatedCreateMemberInvitation:
    email: NormalizedEmail
    role: MembershipRole
    invitation_request_id: UUID
    fingerprint: str


def validate_update_organization(command: UpdateOrganizationCommand) -> ValidatedUpdateOrganization:
    if command.version < 1:
        raise ValueError("La version de l’organisation doit être positive.")
    if command.name is None and command.locale is None and command.timezone is None:
        raise ValueError("Au moins un champ de l’organisation doit être fourni.")

    name = None
    if command.name is not None:
        name = " ".join(command.name.split())
        if not 1 <= len(name) <= 160:
            raise ValueError("Le nom de l’organisation doit contenir entre 1 et 160 caractères.")

    if command.locale is not None and command.locale not in SUPPORTED_LOCALES:
        raise ValueError("La langue de l’organisation doit être fr-CA ou en-CA.")

    if command.timezone is not None:
        try:
            ZoneInfo(command.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Le fuseau horaire doit être un identifiant IANA valide.") from error

    return ValidatedUpdateOrganization(
        version=command.version,
        name=name,
        locale=command.locale,
        timezone=command.timezone,
    )


def validate_update_membership(command: UpdateMembershipCommand) -> UpdateMembershipCommand:
    if command.version < 1:
        raise ValueError("La version de l’appartenance doit être positive.")
    if command.role is None and command.status is None:
        raise ValueError("Le rôle ou l’état de l’appartenance doit être fourni.")
    return command


def validate_change_organization_status(
    command: ChangeOrganizationStatusCommand,
    *,
    operation: str,
) -> ValidatedChangeOrganizationStatus:
    if operation not in {"suspend", "reactivate"}:
        raise ValueError("L’opération de statut d’organisation est inconnue.")
    if command.version < 1:
        raise ValueError("La version de l’organisation doit être positive.")
    external_reference = command.external_reference
    if external_reference is not None:
        external_reference = external_reference.strip()
        if not external_reference:
            external_reference = None
        elif _EXTERNAL_REFERENCE_PATTERN.fullmatch(external_reference) is None:
            raise ValueError("La référence externe ne respecte pas le format autorisé.")
    canonical = json.dumps(
        {
            "external_reference": external_reference,
            "operation": operation,
            "reason_code": command.reason_code.value,
            "version": command.version,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return ValidatedChangeOrganizationStatus(
        operation_id=command.operation_id,
        version=command.version,
        reason_code=command.reason_code,
        external_reference=external_reference,
        fingerprint=hashlib.sha256(canonical.encode("ascii")).hexdigest(),
    )


def validate_create_member_invitation(
    command: CreateMemberInvitationCommand,
) -> ValidatedCreateMemberInvitation:
    email = normalize_email(command.email)
    canonical = json.dumps(
        {"email": email.normalized, "role": command.role.value},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return ValidatedCreateMemberInvitation(
        email=email,
        role=command.role,
        invitation_request_id=command.invitation_request_id,
        fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
