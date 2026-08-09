from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .identity import MembershipRole, NormalizedEmail, normalize_email

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
SUPPORTED_LOCALES = frozenset({"fr-CA", "en-CA"})


class InvitationKind(StrEnum):
    INITIAL_ADMINISTRATOR = "initial_administrator"
    MEMBER = "member"


class InvitationDeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class InvitationState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class InvitationToken:
    raw: str
    hash: str


@dataclass(frozen=True, slots=True)
class ProvisionOrganizationCommand:
    name: str
    locale: str
    timezone: str
    first_administrator_email: str
    creation_request_id: UUID


@dataclass(frozen=True, slots=True)
class ValidatedProvisionOrganization:
    name: str
    locale: str
    timezone: str
    first_administrator_email: NormalizedEmail
    creation_request_id: UUID
    fingerprint: str


@dataclass(frozen=True, slots=True)
class OrganizationProvisioningView:
    id: UUID
    name: str
    locale: str
    timezone: str
    status: str
    version: int
    created_at: datetime
    activated_at: datetime | None


@dataclass(frozen=True, slots=True)
class InvitationProvisioningView:
    id: UUID
    recipient_email: str
    role: MembershipRole
    state: InvitationState
    delivery_status: InvitationDeliveryStatus
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProvisioningView:
    organization: OrganizationProvisioningView
    first_invitation: InvitationProvisioningView
    replayed: bool


@dataclass(frozen=True, slots=True)
class InvitationPreview:
    organization_name: str
    role: MembershipRole
    expires_at: datetime
    existing_account: bool


@dataclass(frozen=True, slots=True)
class AcceptedInvitation:
    user_id: UUID
    user_version: int
    organization_id: UUID
    invitation_id: UUID
    invitation_kind: InvitationKind
    organization_activated: bool


@dataclass(frozen=True, slots=True)
class InvitationMessage:
    recipient_email: str
    organization_name: str
    role: MembershipRole
    expires_at: datetime
    invitation_link: str


def validate_provision_organization(command: ProvisionOrganizationCommand) -> ValidatedProvisionOrganization:
    name = " ".join(command.name.split())
    if not 1 <= len(name) <= 160:
        raise ValueError("Le nom de l’organisation doit contenir entre 1 et 160 caractères.")
    if command.locale not in SUPPORTED_LOCALES:
        raise ValueError("La langue de l’organisation doit être fr-CA ou en-CA.")
    try:
        ZoneInfo(command.timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Le fuseau horaire doit être un identifiant IANA valide.") from error
    email = normalize_email(command.first_administrator_email)
    canonical = json.dumps(
        {
            "email": email.normalized,
            "locale": command.locale,
            "name": name,
            "timezone": command.timezone,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return ValidatedProvisionOrganization(
        name=name,
        locale=command.locale,
        timezone=command.timezone,
        first_administrator_email=email,
        creation_request_id=command.creation_request_id,
        fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def hash_invitation_token(raw_token: str) -> str:
    if len(raw_token) > 128 or TOKEN_PATTERN.fullmatch(raw_token) is None:
        raise ValueError("Le jeton d’invitation est invalide.")
    try:
        decoded = base64.urlsafe_b64decode(f"{raw_token}=")
    except ValueError as error:
        raise ValueError("Le jeton d’invitation est invalide.") from error
    if len(decoded) != 32:
        raise ValueError("Le jeton d’invitation est invalide.")
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


def invitation_state(
    *,
    now: datetime,
    expires_at: datetime,
    accepted_at: datetime | None,
    revoked_at: datetime | None,
) -> InvitationState:
    if accepted_at is not None:
        return InvitationState.ACCEPTED
    if revoked_at is not None:
        return InvitationState.REVOKED
    normalized_now = _as_utc(now)
    if _as_utc(expires_at) <= normalized_now:
        return InvitationState.EXPIRED
    return InvitationState.ACTIVE


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Une date d’invitation doit inclure un fuseau horaire.")
    return value.astimezone(UTC)
