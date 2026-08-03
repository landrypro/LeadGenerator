from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.domain.identity import (
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    PlatformRole,
    UserIdentity,
    UserStatus,
    capabilities_for,
    select_active_organization,
)
from backend.app.domain.organization import (
    CreateMemberInvitationCommand,
    UpdateMembershipCommand,
    UpdateOrganizationCommand,
    validate_create_member_invitation,
    validate_update_membership,
    validate_update_organization,
)

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


def membership(role: MembershipRole, *, created_at: datetime = NOW) -> MembershipIdentity:
    return MembershipIdentity(
        id=uuid4(),
        organization_id=uuid4(),
        organization_name="Entreprise Exemple",
        role=role,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=created_at,
    )


def user(*memberships: MembershipIdentity, platform: bool = False) -> UserIdentity:
    return UserIdentity(
        id=uuid4(),
        email="membre@example.ca",
        display_name="Membre",
        password_hash="hash",
        status=UserStatus.ACTIVE,
        platform_role=PlatformRole.PLATFORM_ADMIN if platform else None,
        last_active_organization_id=None,
        version=1,
        memberships=memberships,
    )


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (
            MembershipRole.ADMIN,
            (
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
        ),
        (
            MembershipRole.MANAGER,
            ("organization:read", "members:read", "audit:read", "google:search", "google:map"),
        ),
        (MembershipRole.SALES, ("organization:read", "google:search", "google:map")),
    ],
)
def test_tenant_capability_matrix_is_exact(role: MembershipRole, expected: tuple[str, ...]) -> None:
    active = membership(role)
    assert capabilities_for(user(active), active) == expected


def test_platform_role_does_not_grant_implicit_tenant_capabilities() -> None:
    assert capabilities_for(user(platform=True), None) == (
        "platform:organizations:read",
        "platform:organizations:create",
    )


def test_active_organization_selection_prefers_valid_preference_then_is_deterministic() -> None:
    first = membership(MembershipRole.SALES)
    second = membership(MembershipRole.MANAGER)
    identity = user(second, first)
    assert (
        select_active_organization(identity)
        == min((first, second), key=lambda item: (item.created_at, str(item.id))).organization_id
    )

    preferred = UserIdentity(
        **{
            field: getattr(identity, field)
            for field in (
                "id",
                "email",
                "display_name",
                "password_hash",
                "status",
                "platform_role",
                "version",
                "memberships",
            )
        },
        last_active_organization_id=second.organization_id,
    )
    assert select_active_organization(preferred) == second.organization_id


def test_organization_command_cleans_values_and_validates_locale_timezone_and_version() -> None:
    validated = validate_update_organization(
        UpdateOrganizationCommand(
            version=2,
            name="  Entreprise   Exemple  ",
            locale="fr-CA",
            timezone="America/Toronto",
        )
    )
    assert validated.name == "Entreprise Exemple"

    for command in (
        UpdateOrganizationCommand(version=0, name="Exemple"),
        UpdateOrganizationCommand(version=1),
        UpdateOrganizationCommand(version=1, locale="fr-FR"),
        UpdateOrganizationCommand(version=1, timezone="Canada/Inexistant"),
    ):
        with pytest.raises(ValueError):
            validate_update_organization(command)


def test_membership_and_invitation_commands_are_strict_domain_values() -> None:
    assert validate_update_membership(UpdateMembershipCommand(version=3, role=MembershipRole.MANAGER)).version == 3
    with pytest.raises(ValueError):
        validate_update_membership(UpdateMembershipCommand(version=1))

    validated = validate_create_member_invitation(
        CreateMemberInvitationCommand(
            email="  ÉQUIPE@Exämple.ca  ",
            role=MembershipRole.SALES,
            invitation_request_id=uuid4(),
        )
    )
    assert validated.email.normalized == "équipe@xn--exmple-cua.ca"
    assert len(validated.fingerprint) == 64
