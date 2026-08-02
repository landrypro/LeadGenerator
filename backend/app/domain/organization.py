from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .identity import MembershipRole, MembershipStatus, NormalizedEmail, normalize_email
from .provisioning import SUPPORTED_LOCALES, InvitationDeliveryStatus, InvitationState


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
