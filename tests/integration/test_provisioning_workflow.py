import asyncio
import base64
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from backend.app.application.ports.provisioning import (
    AcceptanceResultCode,
    ProvisionResultCode,
    ResendResultCode,
    RevokeResultCode,
)
from backend.app.application.tenancy import ActorContext
from backend.app.domain.provisioning import (
    InvitationToken,
    ProvisionOrganizationCommand,
    hash_invitation_token,
    validate_provision_organization,
)
from backend.app.infrastructure.postgres import PostgresDatabase, SqlAlchemyProvisioningGateway

pytestmark = pytest.mark.integration


def database_urls() -> tuple[str, str]:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL applicative et propriétaire sont requises.")
    return app_url, owner_url


def database(url: str, *, pool_size: int = 4) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout_seconds=3,
        statement_timeout_ms=5_000,
    )


def invitation_token() -> InvitationToken:
    raw = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    return InvitationToken(raw, hash_invitation_token(raw))


async def create_platform_actor(owner: PostgresDatabase) -> UUID:
    actor_id = uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash,
                    status, platform_role, created_at, updated_at
                ) VALUES (
                    :id, :email, :email, 'Admin plateforme', 'hash-test',
                    'active', 'platform_admin', :now, :now
                )
                """
            ),
            {"id": actor_id, "email": f"platform-{actor_id}@example.ca", "now": now},
        )
    return actor_id


async def cleanup(
    owner: PostgresDatabase,
    *,
    actor_id: UUID,
    request_id: UUID,
    extra_user_ids: tuple[UUID, ...] = (),
) -> None:
    async with owner.engine.begin() as connection:
        organization_id = await connection.scalar(
            text("SELECT id FROM organizations WHERE creation_request_id = :request_id"),
            {"request_id": request_id},
        )
        accepted_users = []
        if organization_id is not None:
            accepted_users = list(
                (
                    await connection.scalars(
                        text(
                            """
                            SELECT DISTINCT accepted_by FROM user_invitations
                            WHERE organization_id = :organization_id AND accepted_by IS NOT NULL
                            """
                        ),
                        {"organization_id": organization_id},
                    )
                ).all()
            )
            await connection.execute(
                text("DELETE FROM invitation_delivery_attempts WHERE organization_id = :organization_id"),
                {"organization_id": organization_id},
            )
            await connection.execute(
                text("DELETE FROM organizations WHERE id = :organization_id"),
                {"organization_id": organization_id},
            )
        for user_id in set(accepted_users) | set(extra_user_ids):
            await connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
        await connection.execute(text("DELETE FROM users WHERE id = :actor_id"), {"actor_id": actor_id})


async def test_concurrent_provisioning_and_acceptance_are_exactly_once_and_rls_safe() -> None:
    app_url, owner_url = database_urls()
    app = database(app_url)
    owner = database(owner_url, pool_size=1)
    gateway = SqlAlchemyProvisioningGateway(app)
    actor_id = await create_platform_actor(owner)
    request_id = uuid4()
    context = ActorContext(actor_id, "provisioning-concurrency")
    now = datetime.now(UTC).replace(microsecond=0)
    command = validate_provision_organization(
        ProvisionOrganizationCommand(
            "Organisation concurrence",
            "fr-CA",
            "America/Toronto",
            f"new-{uuid4()}@example.ca",
            request_id,
        )
    )
    tokens = (invitation_token(), invitation_token())
    try:
        results = await asyncio.gather(
            *(
                gateway.provision(
                    context=context,
                    command=command,
                    token=tokens[index],
                    organization_id=uuid4(),
                    invitation_id=uuid4(),
                    delivery_attempt_id=uuid4(),
                    expires_at=now + timedelta(days=3),
                    now=now,
                )
                for index in range(2)
            )
        )
        assert {result.code for result in results} == {ProvisionResultCode.CREATED, ProvisionResultCode.REPLAYED}
        created_index = next(
            index for index, result in enumerate(results) if result.code is ProvisionResultCode.CREATED
        )
        created = results[created_index]
        assert created.view is not None and created.delivery_attempt_id is not None

        await gateway.finalize_delivery(
            context=context,
            invitation_id=created.view.first_invitation.id,
            delivery_attempt_id=created.delivery_attempt_id,
            sent=True,
            failure_code=None,
            now=now,
        )
        preview = await gateway.preview(token_hash=tokens[created_index].hash, now=now)
        assert preview is not None and preview.existing_account is False

        acceptance_results = await asyncio.gather(
            *(
                gateway.accept_new_account(
                    token_hash=tokens[created_index].hash,
                    user_id=uuid4(),
                    membership_id=uuid4(),
                    display_name="Premier administrateur",
                    password_hash="argon2-test-hash",
                    now=now,
                )
                for _ in range(2)
            )
        )
        assert sorted(result.code.value for result in acceptance_results) == ["accepted", "invalid"]
        accepted = next(
            result.accepted for result in acceptance_results if result.code is AcceptanceResultCode.ACCEPTED
        )
        assert accepted is not None

        async with owner.engine.connect() as connection:
            organization = (
                (
                    await connection.execute(
                        text("SELECT status, activated_at FROM organizations WHERE id = :id"),
                        {"id": accepted.organization_id},
                    )
                )
                .mappings()
                .one()
            )
            membership_count = await connection.scalar(
                text("SELECT count(*) FROM memberships WHERE organization_id = :id"),
                {"id": accepted.organization_id},
            )
        async with app.unit_of_work() as unit_of_work:
            invisible = await unit_of_work.session.scalar(text("SELECT count(*) FROM invitation_delivery_attempts"))

        assert organization["status"] == "active"
        assert organization["activated_at"] is not None
        assert membership_count == 1
        assert invisible == 0
        assert await gateway.preview(token_hash=tokens[created_index].hash, now=now) is None
    finally:
        await cleanup(owner, actor_id=actor_id, request_id=request_id)
        await app.close()
        await owner.close()


async def test_provisioning_functions_have_narrow_ownership_acl_and_search_path() -> None:
    app_url, owner_url = database_urls()
    app = database(app_url, pool_size=1)
    owner = database(owner_url, pool_size=1)
    function_names = (
        "platform_provision_organization",
        "platform_list_organizations",
        "platform_resend_initial_invitation",
        "platform_revoke_initial_invitation",
        "platform_finalize_invitation_delivery",
        "invitation_preview",
        "accept_invitation_new_account",
        "accept_invitation_existing_account",
    )
    try:
        async with owner.engine.connect() as connection:
            functions = (
                (
                    await connection.execute(
                        text(
                            """
                            SELECT function.proname, owner.rolname, function.prosecdef, function.proconfig
                            FROM pg_proc AS function
                            JOIN pg_namespace AS namespace ON namespace.oid = function.pronamespace
                            JOIN pg_roles AS owner ON owner.oid = function.proowner
                            WHERE namespace.nspname = 'app_private'
                              AND function.proname = ANY(CAST(:names AS text[]))
                            """
                        ),
                        {"names": list(function_names)},
                    )
                )
                .mappings()
                .all()
            )
            public_grants = await connection.scalar(
                text(
                    """
                    SELECT count(*) FROM information_schema.routine_privileges
                    WHERE routine_schema = 'app_private'
                      AND routine_name = ANY(CAST(:names AS text[]))
                      AND grantee = 'PUBLIC'
                    """
                ),
                {"names": list(function_names)},
            )
        async with app.engine.connect() as connection:
            may_delete_attempts = await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'public.invitation_delivery_attempts', 'DELETE')")
            )
    finally:
        await app.close()
        await owner.close()

    assert {row["proname"] for row in functions} == set(function_names)
    assert all(row["rolname"] == "prospect_rls_definer" and row["prosecdef"] for row in functions)
    assert all("search_path=pg_catalog, public, pg_temp" in row["proconfig"] for row in functions)
    assert public_grants == 0
    assert may_delete_attempts is False


async def test_resend_rotates_the_token_and_existing_account_acceptance_activates_the_organization() -> None:
    app_url, owner_url = database_urls()
    app = database(app_url)
    owner = database(owner_url, pool_size=1)
    gateway = SqlAlchemyProvisioningGateway(app)
    actor_id = await create_platform_actor(owner)
    existing_user_id = uuid4()
    request_id = uuid4()
    resend_request_id = uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    email = f"existing-{existing_user_id}@example.ca"
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash,
                    status, created_at, updated_at
                ) VALUES (:id, :email, :email, 'Compte existant', 'hash-test', 'active', :now, :now)
                """
            ),
            {"id": existing_user_id, "email": email, "now": now},
        )
    context = ActorContext(actor_id, "resend")
    first_token = invitation_token()
    replacement_token = invitation_token()
    command = validate_provision_organization(
        ProvisionOrganizationCommand(
            "Organisation existante",
            "fr-CA",
            "America/Toronto",
            email,
            request_id,
        )
    )
    try:
        created = await gateway.provision(
            context=context,
            command=command,
            token=first_token,
            organization_id=uuid4(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(days=3),
            now=now,
        )
        assert created.view is not None
        organization_id = created.view.organization.id
        preview = await gateway.preview(token_hash=first_token.hash, now=now)
        assert preview is not None and preview.existing_account is True

        rate_limited = await gateway.prepare_resend(
            context=context,
            organization_id=organization_id,
            request_id=resend_request_id,
            token=replacement_token,
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(days=3, seconds=30),
            now=now + timedelta(seconds=30),
            cooldown_seconds=60,
            window_seconds=86_400,
            max_per_window=5,
        )
        assert rate_limited.code is ResendResultCode.RATE_LIMITED
        assert rate_limited.retry_after_seconds == 30

        resent = await gateway.prepare_resend(
            context=context,
            organization_id=organization_id,
            request_id=resend_request_id,
            token=replacement_token,
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(days=3, seconds=61),
            now=now + timedelta(seconds=61),
            cooldown_seconds=60,
            window_seconds=86_400,
            max_per_window=5,
        )
        replayed = await gateway.prepare_resend(
            context=context,
            organization_id=organization_id,
            request_id=resend_request_id,
            token=invitation_token(),
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(days=4),
            now=now + timedelta(seconds=62),
            cooldown_seconds=60,
            window_seconds=86_400,
            max_per_window=5,
        )
        assert resent.code is ResendResultCode.CREATED
        assert replayed.code is ResendResultCode.REPLAYED
        assert await gateway.preview(token_hash=first_token.hash, now=now + timedelta(seconds=61)) is None
        assert await gateway.preview(token_hash=replacement_token.hash, now=now + timedelta(seconds=61)) is not None

        accepted = await gateway.accept_existing_account(
            context=ActorContext(existing_user_id, "accept-existing"),
            token_hash=replacement_token.hash,
            membership_id=uuid4(),
            now=now + timedelta(seconds=62),
        )
        assert accepted.code is AcceptanceResultCode.ACCEPTED
        assert accepted.accepted is not None and accepted.accepted.user_version == 2
        revoked = await gateway.revoke_initial_invitation(
            context=context,
            organization_id=organization_id,
            now=now + timedelta(seconds=63),
        )
        assert revoked.code is RevokeResultCode.ALREADY_ACCEPTED
    finally:
        await cleanup(
            owner,
            actor_id=actor_id,
            request_id=request_id,
            extra_user_ids=(existing_user_id,),
        )
        await app.close()
        await owner.close()
