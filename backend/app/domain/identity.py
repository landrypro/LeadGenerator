from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class InvalidEmail(ValueError):
    """Le courriel ne peut pas être utilisé comme identité."""


class InvalidPassword(ValueError):
    """Le mot de passe ne respecte pas la politique minimale."""


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class OrganizationStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class MembershipRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"


class PlatformRole(StrEnum):
    PLATFORM_ADMIN = "platform_admin"


@dataclass(frozen=True, slots=True)
class NormalizedEmail:
    display: str
    normalized: str


@dataclass(frozen=True, slots=True)
class MembershipIdentity:
    id: UUID
    organization_id: UUID
    organization_name: str
    role: MembershipRole
    status: MembershipStatus
    organization_status: OrganizationStatus
    created_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status is MembershipStatus.ACTIVE and self.organization_status is OrganizationStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class UserIdentity:
    id: UUID
    email: str
    display_name: str
    password_hash: str | None
    status: UserStatus
    platform_role: PlatformRole | None
    last_active_organization_id: UUID | None
    version: int
    memberships: tuple[MembershipIdentity, ...]

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE and self.password_hash is not None


@dataclass(frozen=True, slots=True)
class SessionRecord:
    user_id: UUID
    active_organization_id: UUID | None
    issued_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    csrf_token: str
    user_version: int


@dataclass(frozen=True, slots=True)
class CreatedSession:
    token: str
    record: SessionRecord


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    user: UserIdentity
    active_membership: MembershipIdentity | None
    csrf_token: str


CAPABILITIES_BY_ROLE: dict[MembershipRole, tuple[str, ...]] = {
    MembershipRole.ADMIN: (
        "organization:read",
        "organization:update",
        "members:read",
        "members:manage",
        "invitations:read",
        "invitations:manage",
        "audit:read",
        "google:search",
        "google:map",
    ),
    MembershipRole.MANAGER: (
        "organization:read",
        "members:read",
        "audit:read",
        "google:search",
        "google:map",
    ),
    MembershipRole.SALES: (
        "organization:read",
        "google:search",
        "google:map",
    ),
}


def normalize_email(value: str) -> NormalizedEmail:
    display = unicodedata.normalize("NFKC", value).strip()
    if not display or len(display) > 254 or any(character.isspace() or ord(character) < 32 for character in display):
        raise InvalidEmail("Le courriel est invalide.")

    local_part, separator, domain = display.rpartition("@")
    if not separator or not local_part or not domain or "@" in local_part or len(local_part) > 64:
        raise InvalidEmail("Le courriel est invalide.")

    try:
        ascii_domain = domain.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as error:
        raise InvalidEmail("Le courriel est invalide.") from error
    if not ascii_domain or len(ascii_domain) > 253 or "." not in ascii_domain:
        raise InvalidEmail("Le courriel est invalide.")
    labels = ascii_domain.split(".")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        raise InvalidEmail("Le courriel est invalide.")

    normalized_local = unicodedata.normalize("NFKC", local_part).casefold()
    normalized = f"{normalized_local}@{ascii_domain}"
    if len(normalized) > 254:
        raise InvalidEmail("Le courriel est invalide.")
    return NormalizedEmail(display=display, normalized=normalized)


def validate_new_password(password: str) -> None:
    if not 12 <= len(password) <= 128:
        raise InvalidPassword("Le mot de passe doit contenir entre 12 et 128 caractères.")


def select_active_organization(user: UserIdentity) -> UUID | None:
    active_memberships = tuple(membership for membership in user.memberships if membership.is_active)
    if user.last_active_organization_id is not None and any(
        membership.organization_id == user.last_active_organization_id for membership in active_memberships
    ):
        return user.last_active_organization_id
    if not active_memberships:
        return None
    return min(active_memberships, key=lambda membership: (membership.created_at, str(membership.id))).organization_id


def capabilities_for(identity: UserIdentity, active_membership: MembershipIdentity | None) -> tuple[str, ...]:
    capabilities: list[str] = []
    if identity.platform_role is PlatformRole.PLATFORM_ADMIN:
        capabilities.extend(
            (
                "platform:organizations:read",
                "platform:organizations:create",
                "platform:organizations:manage",
                "platform:audit:read",
            )
        )
    if active_membership is not None and active_membership.is_active:
        capabilities.extend(CAPABILITIES_BY_ROLE[active_membership.role])
    return tuple(capabilities)
