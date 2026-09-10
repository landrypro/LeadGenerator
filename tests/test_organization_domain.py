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
    ChangeOrganizationStatusCommand,
    CreateMemberInvitationCommand,
    OrganizationStatusReasonCode,
    UpdateMembershipCommand,
    UpdateOrganizationCommand,
    validate_change_organization_status,
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
                "prospects:read",
                "prospects:create",
                "prospects:update",
                "pipeline:read",
                "pipeline:move",
                "pipeline:history:read",
                "pipeline:reopen",
                "pipeline:configure",
                "contacts:read",
                "contacts:write",
                "compliance:read",
                "permissions:restrict",
                "permissions:allow",
                "providers:read",
                "providers:manage",
                "acquisitions:declare",
                "acquisitions:review",
                "retention:read",
                "retention:manage",
                "retention:hold:create",
                "retention:hold:release",
                "imports:read",
                "imports:declare",
                "imports:archive",
                "prospects:archive",
                "contacts:archive",
                "activities:read",
                "activities:create",
                "activities:correct:self",
                "activities:correct:any",
                "tasks:read",
                "tasks:create",
                "tasks:update:assigned",
                "tasks:manage",
            ),
        ),
        (
            MembershipRole.MANAGER,
            (
                "organization:read",
                "members:read",
                "audit:read",
                "google:search",
                "google:map",
                "prospects:read",
                "prospects:create",
                "prospects:update",
                "pipeline:read",
                "pipeline:move",
                "pipeline:history:read",
                "pipeline:reopen",
                "contacts:read",
                "contacts:write",
                "compliance:read",
                "permissions:restrict",
                "permissions:allow",
                "providers:read",
                "acquisitions:declare",
                "retention:read",
                "retention:hold:create",
                "imports:read",
                "imports:declare",
                "prospects:archive",
                "contacts:archive",
                "activities:read",
                "activities:create",
                "activities:correct:self",
                "activities:correct:any",
                "tasks:read",
                "tasks:create",
                "tasks:update:assigned",
                "tasks:manage",
            ),
        ),
        (
            MembershipRole.SALES,
            (
                "organization:read",
                "google:search",
                "google:map",
                "prospects:read",
                "prospects:create",
                "prospects:update",
                "pipeline:read",
                "pipeline:move",
                "pipeline:history:read",
                "contacts:read",
                "contacts:write",
                "permissions:restrict",
                "activities:read",
                "activities:create",
                "activities:correct:self",
                "tasks:read",
                "tasks:create",
                "tasks:update:assigned",
            ),
        ),
    ],
)
def test_tenant_capability_matrix_is_exact(role: MembershipRole, expected: tuple[str, ...]) -> None:
    active = membership(role)
    assert capabilities_for(user(active), active) == expected


def test_platform_role_does_not_grant_implicit_tenant_capabilities() -> None:
    assert capabilities_for(user(platform=True), None) == (
        "platform:organizations:read",
        "platform:organizations:create",
        "platform:organizations:manage",
        "platform:audit:read",
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


def test_organization_status_command_is_canonical_and_rejects_free_text_reference() -> None:
    operation_id = uuid4()
    validated = validate_change_organization_status(
        ChangeOrganizationStatusCommand(
            operation_id=operation_id,
            version=3,
            reason_code=OrganizationStatusReasonCode.ADMINISTRATIVE,
            external_reference=" TICKET-123 ",
        ),
        operation="suspend",
    )
    assert validated.operation_id == operation_id
    assert validated.external_reference == "TICKET-123"
    assert len(validated.fingerprint) == 64

    with pytest.raises(ValueError):
        validate_change_organization_status(
            ChangeOrganizationStatusCommand(
                operation_id=operation_id,
                version=0,
                reason_code=OrganizationStatusReasonCode.ADMINISTRATIVE,
            ),
            operation="suspend",
        )
    with pytest.raises(ValueError):
        validate_change_organization_status(
            ChangeOrganizationStatusCommand(
                operation_id=operation_id,
                version=1,
                reason_code=OrganizationStatusReasonCode.ADMINISTRATIVE,
                external_reference="contient un espace",
            ),
            operation="reactivate",
        )
