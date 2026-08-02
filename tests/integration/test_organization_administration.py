import asyncio
import base64
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from backend.app.application.ports.organization import (
    CreateMemberInvitationResultCode,
    MemberInvitationMutationResultCode,
    SwitchOrganizationResultCode,
    UpdateMembershipResultCode,
    UpdateOrganizationResultCode,
)
from backend.app.application.ports.provisioning import AcceptanceResultCode
from backend.app.application.tenancy import ActorContext, TenantContext
from backend.app.domain.identity import MembershipRole, MembershipStatus
from backend.app.domain.organization import (
    CreateMemberInvitationCommand,
    UpdateMembershipCommand,
    UpdateOrganizationCommand,
    validate_create_member_invitation,
    validate_update_organization,
)
from backend.app.domain.provisioning import InvitationToken, hash_invitation_token
from backend.app.infrastructure.postgres import (
    PostgresDatabase,
    SqlAlchemyOrganizationAdministrationGateway,
    SqlAlchemyProvisioningGateway,
)

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class Fixture:
    organization_a: UUID
    organization_b: UUID
    admin_a: UUID
    admin_b: UUID
    membership_a: UUID
    membership_b: UUID
    membership_other: UUID


def _urls() -> tuple[str, str]:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("PostgreSQL réel est requis.")
    return app_url, owner_url


def _database(url: str, pool_size: int = 4) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout_seconds=3,
        statement_timeout_ms=5_000,
    )


async def _fixture(owner: PostgresDatabase) -> Fixture:
    result = Fixture(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4())
    parameters = asdict(result)
    now = datetime.now(UTC).replace(microsecond=0)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash, status,
                    last_active_organization_id, created_at, updated_at, version
                ) VALUES
                    (:admin_a, :email_a, :email_a, 'Admin A', 'hash-a', 'active',
                     NULL, :now, :now, 1),
                    (:admin_b, :email_b, :email_b, 'Admin B', 'hash-b', 'active',
                     NULL, :now, :now, 1)
                """
            ),
            {
                **parameters,
                "email_a": f"a-{result.admin_a}@example.ca",
                "email_b": f"b-{result.admin_b}@example.ca",
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO organizations (
                    id, name, locale, timezone, status, created_by, activated_at,
                    created_at, updated_at, version
                ) VALUES
                    (:organization_a, 'Organisation A', 'fr-CA', 'America/Toronto', 'active',
                     :admin_a, :now, :now, :now, 1),
                    (:organization_b, 'Organisation B', 'fr-CA', 'America/Toronto', 'active',
                     :admin_a, :now, :now, :now, 1)
                """
            ),
            {**parameters, "now": now},
        )
        await connection.execute(
            text(
                """
                UPDATE users SET last_active_organization_id = :organization_a
                WHERE id IN (:admin_a, :admin_b)
                """
            ),
            parameters,
        )
        await connection.execute(
            text(
                """
                INSERT INTO memberships (
                    id, organization_id, user_id, role, status, created_by, updated_by,
                    created_at, updated_at, version
                ) VALUES
                    (:membership_a, :organization_a, :admin_a, 'admin', 'active',
                     :admin_a, :admin_a, :now, :now, 1),
                    (:membership_b, :organization_a, :admin_b, 'admin', 'active',
                     :admin_a, :admin_a, :now, :now, 1),
                    (:membership_other, :organization_b, :admin_a, 'sales', 'active',
                     :admin_a, :admin_a, :now, :now, 1)
                """
            ),
            {**parameters, "now": now},
        )
    return result


async def _cleanup(owner: PostgresDatabase, fixture: Fixture) -> None:
    async with owner.engine.begin() as connection:
        accepted = list(
            (
                await connection.scalars(
                    text(
                        """
                        SELECT accepted_by FROM user_invitations
                        WHERE organization_id IN (:organization_a, :organization_b)
                          AND accepted_by IS NOT NULL
                        """
                    ),
                    asdict(fixture),
                )
            ).all()
        )
        await connection.execute(
            text(
                "DELETE FROM invitation_delivery_attempts WHERE organization_id IN (:organization_a, :organization_b)"
            ),
            asdict(fixture),
        )
        await connection.execute(
            text("DELETE FROM organizations WHERE id IN (:organization_a, :organization_b)"),
            asdict(fixture),
        )
        for user_id in set(accepted) | {fixture.admin_a, fixture.admin_b}:
            await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


def _token() -> InvitationToken:
    raw = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    return InvitationToken(raw=raw, hash=hash_invitation_token(raw))


async def test_organization_member_invitation_and_switch_contracts() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _fixture(owner)
    gateway = SqlAlchemyOrganizationAdministrationGateway(app)
    invitations = SqlAlchemyProvisioningGateway(app)
    context = TenantContext(fixture.admin_a, fixture.organization_a, uuid4().hex)
    now = datetime.now(UTC).replace(microsecond=0)
    invitee_id = uuid4()
    try:
        organization = await gateway.get_organization(context=context)
        assert organization is not None
        updated = await gateway.update_organization(
            context=context,
            command=validate_update_organization(UpdateOrganizationCommand(version=1, name="Organisation A2")),
            now=now,
        )
        assert updated.code is UpdateOrganizationResultCode.UPDATED
        assert updated.organization is not None and updated.organization.version == 2

        members = await gateway.list_members(
            context=context,
            after_created_at=None,
            after_id=None,
            limit=10,
        )
        assert {member.membership_id for member in members} == {fixture.membership_a, fixture.membership_b}

        invitation_token = _token()
        request_id = uuid4()
        command = validate_create_member_invitation(
            CreateMemberInvitationCommand(
                email=f"invite-{uuid4()}@example.ca",
                role=MembershipRole.MANAGER,
                invitation_request_id=request_id,
            )
        )
        created = await gateway.create_invitation(
            context=context,
            command=command,
            token=invitation_token,
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
        )
        replayed = await gateway.create_invitation(
            context=context,
            command=command,
            token=_token(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
        )
        assert created.code is CreateMemberInvitationResultCode.CREATED
        assert replayed.code is CreateMemberInvitationResultCode.REPLAYED
        assert created.invitation is not None and replayed.invitation is not None
        assert created.invitation.id == replayed.invitation.id

        preview = await invitations.preview(token_hash=invitation_token.hash, now=now)
        assert preview is not None and preview.role is MembershipRole.MANAGER
        accepted = await invitations.accept_new_account(
            token_hash=invitation_token.hash,
            user_id=invitee_id,
            membership_id=uuid4(),
            display_name="Gestionnaire",
            password_hash="hash-test",
            now=now,
        )
        assert accepted.code is AcceptanceResultCode.ACCEPTED
        async with owner.engine.connect() as connection:
            role = await connection.scalar(
                text("SELECT role FROM memberships WHERE organization_id = :organization_id AND user_id = :user_id"),
                {"organization_id": fixture.organization_a, "user_id": invitee_id},
            )
            status = await connection.scalar(
                text("SELECT status FROM organizations WHERE id = :id"),
                {"id": fixture.organization_a},
            )
        assert role == "manager"
        assert status == "active"

        switched = await gateway.switch_organization(
            context=ActorContext(fixture.admin_a, uuid4().hex),
            membership_id=fixture.membership_other,
            now=now,
        )
        assert switched.code is SwitchOrganizationResultCode.SWITCHED
        assert switched.organization_id == fixture.organization_b
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()


async def test_two_concurrent_self_demotions_keep_one_active_administrator() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _fixture(owner)
    gateway = SqlAlchemyOrganizationAdministrationGateway(app)
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        first, second = await asyncio.gather(
            gateway.update_membership(
                context=TenantContext(fixture.admin_a, fixture.organization_a, uuid4().hex),
                membership_id=fixture.membership_a,
                command=UpdateMembershipCommand(version=1, role=MembershipRole.MANAGER),
                now=now,
            ),
            gateway.update_membership(
                context=TenantContext(fixture.admin_b, fixture.organization_a, uuid4().hex),
                membership_id=fixture.membership_b,
                command=UpdateMembershipCommand(version=1, status=MembershipStatus.DISABLED),
                now=now,
            ),
        )
        assert {first.code, second.code} == {
            UpdateMembershipResultCode.UPDATED,
            UpdateMembershipResultCode.LAST_ACTIVE_ADMINISTRATOR,
        }
        async with owner.engine.connect() as connection:
            active_admins = await connection.scalar(
                text(
                    """
                    SELECT COUNT(*) FROM memberships
                    WHERE organization_id = :organization_id AND role = 'admin' AND status = 'active'
                    """
                ),
                {"organization_id": fixture.organization_a},
            )
        assert active_admins == 1
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()


async def test_versions_conflicts_member_invitation_lifecycle_and_cross_scope_are_enforced() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _fixture(owner)
    gateway = SqlAlchemyOrganizationAdministrationGateway(app)
    invitations = SqlAlchemyProvisioningGateway(app)
    context = TenantContext(fixture.admin_a, fixture.organization_a, uuid4().hex)
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        unchanged_organization = await gateway.update_organization(
            context=context,
            command=validate_update_organization(UpdateOrganizationCommand(version=1, name="Organisation A")),
            now=now,
        )
        stale_organization = await gateway.update_organization(
            context=context,
            command=validate_update_organization(UpdateOrganizationCommand(version=99, name="Organisation A3")),
            now=now,
        )
        assert unchanged_organization.code is UpdateOrganizationResultCode.UNCHANGED
        assert unchanged_organization.organization is not None
        assert unchanged_organization.organization.version == 1
        assert stale_organization.code is UpdateOrganizationResultCode.VERSION_CONFLICT
        assert stale_organization.current_version == 1

        unchanged_member = await gateway.update_membership(
            context=context,
            membership_id=fixture.membership_b,
            command=UpdateMembershipCommand(version=1, role=MembershipRole.ADMIN),
            now=now,
        )
        cross_member = await gateway.update_membership(
            context=context,
            membership_id=fixture.membership_other,
            command=UpdateMembershipCommand(version=1, role=MembershipRole.MANAGER),
            now=now,
        )
        assert unchanged_member.code is UpdateMembershipResultCode.UNCHANGED
        assert unchanged_member.user_version is None
        assert cross_member.code is UpdateMembershipResultCode.NOT_FOUND

        active_member_command = validate_create_member_invitation(
            CreateMemberInvitationCommand(
                email=f"b-{fixture.admin_b}@example.ca",
                role=MembershipRole.SALES,
                invitation_request_id=uuid4(),
            )
        )
        active_member = await gateway.create_invitation(
            context=context,
            command=active_member_command,
            token=_token(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
        )
        assert active_member.code is CreateMemberInvitationResultCode.MEMBERSHIP_ALREADY_ACTIVE

        disabled_member = await gateway.update_membership(
            context=context,
            membership_id=fixture.membership_b,
            command=UpdateMembershipCommand(version=1, status=MembershipStatus.DISABLED),
            now=now,
        )
        stale_member = await gateway.update_membership(
            context=context,
            membership_id=fixture.membership_b,
            command=UpdateMembershipCommand(version=1, role=MembershipRole.MANAGER),
            now=now,
        )
        disabled_invitation = await gateway.create_invitation(
            context=context,
            command=validate_create_member_invitation(
                CreateMemberInvitationCommand(
                    f"b-{fixture.admin_b}@example.ca",
                    MembershipRole.SALES,
                    uuid4(),
                )
            ),
            token=_token(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
        )
        assert disabled_member.code is UpdateMembershipResultCode.UPDATED
        assert stale_member.code is UpdateMembershipResultCode.VERSION_CONFLICT
        assert stale_member.current_version == 2
        assert disabled_invitation.code is CreateMemberInvitationResultCode.MEMBERSHIP_REACTIVATION_REQUIRED

        raw_token = _token()
        recipient = f"lifecycle-{uuid4()}@example.ca"
        created_request_id = uuid4()
        created = await gateway.create_invitation(
            context=context,
            command=validate_create_member_invitation(
                CreateMemberInvitationCommand(recipient, MembershipRole.SALES, created_request_id)
            ),
            token=raw_token,
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
        )
        assert created.code is CreateMemberInvitationResultCode.CREATED
        assert created.invitation is not None

        collision = await gateway.create_invitation(
            context=context,
            command=validate_create_member_invitation(
                CreateMemberInvitationCommand(
                    f"collision-{uuid4()}@example.ca",
                    MembershipRole.SALES,
                    created_request_id,
                )
            ),
            token=_token(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
        )
        assert collision.code is CreateMemberInvitationResultCode.IDEMPOTENCY_CONFLICT

        immediate_resend = await gateway.resend_invitation(
            context=context,
            invitation_id=created.invitation.id,
            request_id=uuid4(),
            token=_token(),
            replacement_invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
            cooldown_seconds=60,
            window_seconds=86_400,
            max_per_window=5,
        )
        assert immediate_resend.code is MemberInvitationMutationResultCode.RATE_LIMITED

        pending = await gateway.create_invitation(
            context=context,
            command=validate_create_member_invitation(
                CreateMemberInvitationCommand(recipient, MembershipRole.SALES, uuid4())
            ),
            token=_token(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(hours=72),
            now=now,
        )
        assert pending.code is CreateMemberInvitationResultCode.INVITATION_ALREADY_PENDING

        replacement_token = _token()
        resend_request_id = uuid4()
        resend_at = now + timedelta(seconds=61)
        resent = await gateway.resend_invitation(
            context=context,
            invitation_id=created.invitation.id,
            request_id=resend_request_id,
            token=replacement_token,
            replacement_invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=resend_at + timedelta(hours=72),
            now=resend_at,
            cooldown_seconds=60,
            window_seconds=86_400,
            max_per_window=5,
        )
        replayed = await gateway.resend_invitation(
            context=context,
            invitation_id=created.invitation.id,
            request_id=resend_request_id,
            token=_token(),
            replacement_invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=resend_at + timedelta(hours=72),
            now=resend_at,
            cooldown_seconds=60,
            window_seconds=86_400,
            max_per_window=5,
        )
        assert resent.code is MemberInvitationMutationResultCode.CREATED
        assert replayed.code is MemberInvitationMutationResultCode.REPLAYED
        assert resent.invitation is not None and replayed.invitation is not None
        assert resent.invitation.id == replayed.invitation.id
        assert await invitations.preview(token_hash=raw_token.hash, now=resend_at) is None
        assert await invitations.preview(token_hash=replacement_token.hash, now=resend_at) is not None

        independent = await gateway.create_invitation(
            context=context,
            command=validate_create_member_invitation(
                CreateMemberInvitationCommand(
                    f"independent-{uuid4()}@example.ca",
                    MembershipRole.MANAGER,
                    uuid4(),
                )
            ),
            token=_token(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=resend_at + timedelta(hours=72),
            now=resend_at,
        )
        assert independent.code is CreateMemberInvitationResultCode.CREATED
        assert independent.invitation is not None
        independent_resend_at = resend_at + timedelta(seconds=61)
        independent_resent = await gateway.resend_invitation(
            context=context,
            invitation_id=independent.invitation.id,
            request_id=uuid4(),
            token=_token(),
            replacement_invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=independent_resend_at + timedelta(hours=72),
            now=independent_resend_at,
            cooldown_seconds=60,
            window_seconds=86_400,
            max_per_window=1,
        )
        assert independent_resent.code is MemberInvitationMutationResultCode.CREATED
        assert independent_resent.invitation is not None

        revoked = await gateway.revoke_invitation(
            context=context,
            invitation_id=resent.invitation.id,
            now=resend_at,
        )
        revoked_again = await gateway.revoke_invitation(
            context=context,
            invitation_id=resent.invitation.id,
            now=resend_at,
        )
        assert revoked.code is MemberInvitationMutationResultCode.REVOKED
        assert revoked_again.code is MemberInvitationMutationResultCode.ALREADY_REVOKED
        independent_revoked = await gateway.revoke_invitation(
            context=context,
            invitation_id=independent_resent.invitation.id,
            now=independent_resend_at,
        )
        assert independent_revoked.code is MemberInvitationMutationResultCode.REVOKED
        assert (
            await gateway.list_invitations(
                context=context,
                after_created_at=None,
                after_id=None,
                limit=25,
                now=resend_at,
            )
            == ()
        )

        cross_switch = await gateway.switch_organization(
            context=ActorContext(fixture.admin_a, uuid4().hex),
            membership_id=fixture.membership_b,
            now=now,
        )
        assert cross_switch.code is SwitchOrganizationResultCode.NOT_FOUND
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()
