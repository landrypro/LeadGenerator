"""Ajouter le provisioning idempotent et les invitations initiales.

Revision ID: 20260723_0004
Revises: 20260723_0003
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0004"
down_revision: str | None = "20260723_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _preflight()
    _upgrade_tables()
    _create_functions()
    _grant_permissions()


def _preflight() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.user_invitations) THEN
                RAISE EXCEPTION
                    'La migration 0004 refuse d inventer un état de livraison pour des invitations héritées.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM public.organizations AS organization
                WHERE organization.status = 'active'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.memberships AS membership
                      WHERE membership.organization_id = organization.id
                        AND membership.role = 'admin'
                        AND membership.status = 'active'
                  )
            ) THEN
                RAISE EXCEPTION
                    'Une organisation active historique ne possède aucun Administrateur actif.';
            END IF;
        END
        $checks$;
        """
    )


def _upgrade_tables() -> None:
    op.add_column("organizations", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.add_column("organizations", sa.Column("creation_request_id", sa.Uuid(), nullable=True))
    op.add_column("organizations", sa.Column("creation_request_fingerprint", sa.String(length=64), nullable=True))
    op.add_column("organizations", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE public.organizations AS organization
        SET created_by = (
                SELECT membership.created_by
                FROM public.memberships AS membership
                WHERE membership.organization_id = organization.id
                ORDER BY membership.created_at, membership.id
                LIMIT 1
            ),
            activated_at = CASE
                WHEN organization.status IN ('active', 'suspended') THEN organization.created_at
                ELSE NULL
            END
        """
    )
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.organizations WHERE created_by IS NULL) THEN
                RAISE EXCEPTION
                    'Impossible de déterminer created_by pour une organisation historique.';
            END IF;
        END
        $checks$;
        """
    )
    op.alter_column("organizations", "created_by", nullable=False)
    op.create_foreign_key(
        op.f("fk_organizations_created_by_users"),
        "organizations",
        "users",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(op.f("uq_organizations_creation_request_id"), "organizations", ["creation_request_id"])
    op.create_check_constraint(
        op.f("ck_organizations_creation_idempotency_consistent"),
        "organizations",
        "(creation_request_id IS NULL) = (creation_request_fingerprint IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_organizations_creation_request_fingerprint_length"),
        "organizations",
        "creation_request_fingerprint IS NULL OR char_length(creation_request_fingerprint) = 64",
    )
    op.drop_constraint(op.f("ck_organizations_status_allowed"), "organizations", type_="check")
    op.create_check_constraint(
        op.f("ck_organizations_status_allowed"),
        "organizations",
        "status IN ('provisioning', 'active', 'suspended')",
    )
    op.create_check_constraint(
        op.f("ck_organizations_activation_state_consistent"),
        "organizations",
        "(status = 'provisioning' AND activated_at IS NULL) OR "
        "(status IN ('active', 'suspended') AND activated_at IS NOT NULL)",
    )
    op.alter_column("organizations", "status", server_default=sa.text("'provisioning'"))

    op.create_unique_constraint(
        op.f("uq_memberships_organization_id_id"),
        "memberships",
        ["organization_id", "id"],
    )

    op.add_column("user_invitations", sa.Column("invitation_kind", sa.String(length=32), nullable=False))
    op.add_column(
        "user_invitations",
        sa.Column("delivery_status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
    )
    op.add_column("user_invitations", sa.Column("accepted_by", sa.Uuid(), nullable=True))
    op.add_column("user_invitations", sa.Column("supersedes_invitation_id", sa.Uuid(), nullable=True))
    op.add_column("user_invitations", sa.Column("delivery_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_invitations", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "user_invitations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_user_invitations_invitation_kind_allowed"),
        "user_invitations",
        "invitation_kind IN ('initial_administrator', 'member')",
    )
    op.create_check_constraint(
        op.f("ck_user_invitations_delivery_status_allowed"),
        "user_invitations",
        "delivery_status IN ('pending', 'sent', 'failed')",
    )
    op.create_check_constraint(
        op.f("ck_user_invitations_terminal_state_exclusive"),
        "user_invitations",
        "NOT (accepted_at IS NOT NULL AND revoked_at IS NOT NULL)",
    )
    op.create_foreign_key(
        op.f("fk_user_invitations_accepted_by_users"),
        "user_invitations",
        "users",
        ["accepted_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        op.f("uq_user_invitations_organization_id_id"),
        "user_invitations",
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        op.f("fk_user_invitations_organization_id_supersedes_invitation_id_user_invitations"),
        "user_invitations",
        "user_invitations",
        ["organization_id", "supersedes_invitation_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "invitation_delivery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('initial', 'resend')",
            name=op.f("ck_invitation_delivery_attempts_kind_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name=op.f("ck_invitation_delivery_attempts_status_allowed"),
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR char_length(failure_code) BETWEEN 1 AND 64",
            name=op.f("ck_invitation_delivery_attempts_failure_code_length"),
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND completed_at IS NULL) OR (status <> 'pending' AND completed_at IS NOT NULL)",
            name=op.f("ck_invitation_delivery_attempts_completion_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_invitation_delivery_attempts_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "invitation_id"],
            ["user_invitations.organization_id", "user_invitations.id"],
            name=op.f("fk_invitation_delivery_attempts_organization_id_invitation_id_user_invitations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_invitation_delivery_attempts_requested_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitation_delivery_attempts")),
        sa.UniqueConstraint("invitation_id", name=op.f("uq_invitation_delivery_attempts_invitation_id")),
        sa.UniqueConstraint("request_id", name=op.f("uq_invitation_delivery_attempts_request_id")),
    )
    op.create_index(
        "ix_invitation_delivery_attempts_org_kind_created",
        "invitation_delivery_attempts",
        ["organization_id", "kind", "created_at"],
        unique=False,
    )
    op.execute("ALTER TABLE public.invitation_delivery_attempts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.invitation_delivery_attempts FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY invitation_delivery_attempts_tenant_isolation
        ON public.invitation_delivery_attempts
        FOR ALL
        TO prospect_app
        USING (organization_id = app_private.current_organization_id())
        WITH CHECK (organization_id = app_private.current_organization_id())
        """
    )


def _create_functions() -> None:
    _execute_function(
        """
        CREATE FUNCTION app_private.is_platform_actor()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
            SELECT EXISTS (
                SELECT 1
                FROM public.users AS actor
                WHERE actor.id = app_private.current_actor_id()
                  AND actor.status = 'active'
                  AND actor.platform_role = 'platform_admin'
            )
        $function$;
        """,
        "app_private.is_platform_actor()",
    )
    _execute_function(
        """
        CREATE FUNCTION app_private.platform_provisioning_view(
            p_organization_id uuid,
            p_now timestamp with time zone
        )
        RETURNS TABLE (
            organization_id uuid,
            organization_name text,
            organization_locale text,
            organization_timezone text,
            organization_status text,
            organization_version integer,
            organization_created_at timestamp with time zone,
            organization_activated_at timestamp with time zone,
            invitation_id uuid,
            recipient_email text,
            invitation_role text,
            invitation_state text,
            invitation_delivery_status text,
            invitation_expires_at timestamp with time zone
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
            SELECT
                organization.id,
                organization.name::text,
                organization.locale::text,
                organization.timezone::text,
                organization.status::text,
                organization.version,
                organization.created_at,
                organization.activated_at,
                invitation.id,
                invitation.email::text,
                invitation.role::text,
                CASE
                    WHEN invitation.accepted_at IS NOT NULL THEN 'accepted'
                    WHEN invitation.revoked_at IS NOT NULL THEN 'revoked'
                    WHEN invitation.expires_at <= p_now THEN 'expired'
                    ELSE 'active'
                END,
                invitation.delivery_status::text,
                invitation.expires_at
            FROM public.organizations AS organization
            JOIN LATERAL (
                SELECT candidate.*
                FROM public.user_invitations AS candidate
                WHERE candidate.organization_id = organization.id
                  AND candidate.invitation_kind = 'initial_administrator'
                ORDER BY candidate.created_at DESC, candidate.id DESC
                LIMIT 1
            ) AS invitation ON true
            WHERE organization.id = p_organization_id
        $function$;
        """,
        "app_private.platform_provisioning_view(uuid, timestamp with time zone)",
    )
    _execute_function(
        _PROVISION_FUNCTION,
        "app_private.platform_provision_organization(uuid, uuid, uuid, text, text, text, text, text, uuid, text, text, timestamp with time zone, timestamp with time zone)",
    )
    _execute_function(
        _LIST_FUNCTION,
        "app_private.platform_list_organizations(timestamp with time zone, uuid, integer, timestamp with time zone)",
    )
    _execute_function(
        _RESEND_FUNCTION,
        "app_private.platform_resend_initial_invitation(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)",
    )
    _execute_function(
        _REVOKE_FUNCTION,
        "app_private.platform_revoke_initial_invitation(uuid, timestamp with time zone)",
    )
    _execute_function(
        _FINALIZE_FUNCTION,
        "app_private.platform_finalize_invitation_delivery(uuid, uuid, boolean, text, timestamp with time zone)",
    )
    _execute_function(
        _PREVIEW_FUNCTION,
        "app_private.invitation_preview(text, timestamp with time zone)",
    )
    _execute_function(
        _ACCEPT_NEW_FUNCTION,
        "app_private.accept_invitation_new_account(text, uuid, uuid, text, text, timestamp with time zone)",
    )
    _execute_function(
        _ACCEPT_EXISTING_FUNCTION,
        "app_private.accept_invitation_existing_account(text, uuid, timestamp with time zone)",
    )


def _execute_function(definition: str, signature: str) -> None:
    create_statement = definition.rsplit("\nALTER FUNCTION", maxsplit=1)[0].strip()
    op.execute(create_statement)
    op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")


_PROVISION_FUNCTION = """
CREATE FUNCTION app_private.platform_provision_organization(
    p_organization_id uuid,
    p_invitation_id uuid,
    p_delivery_attempt_id uuid,
    p_name text,
    p_locale text,
    p_timezone text,
    p_email text,
    p_email_normalized text,
    p_creation_request_id uuid,
    p_fingerprint text,
    p_token_hash text,
    p_expires_at timestamp with time zone,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_existing public.organizations%ROWTYPE;
    v_view jsonb;
BEGIN
    IF NOT app_private.is_platform_actor() THEN
        RAISE EXCEPTION 'platform capability required' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_creation_request_id::text, 0));

    SELECT * INTO v_existing
    FROM public.organizations
    WHERE creation_request_id = p_creation_request_id;

    IF FOUND THEN
        IF v_existing.creation_request_fingerprint <> p_fingerprint THEN
            RETURN pg_catalog.jsonb_build_object('code', 'idempotency_conflict');
        END IF;
        SELECT pg_catalog.to_jsonb(view) INTO v_view
        FROM app_private.platform_provisioning_view(v_existing.id, p_now) AS view;
        RETURN pg_catalog.jsonb_build_object('code', 'replayed', 'view', v_view);
    END IF;

    INSERT INTO public.organizations (
        id, name, locale, timezone, status, created_by, creation_request_id,
        creation_request_fingerprint, created_at, updated_at, version
    ) VALUES (
        p_organization_id, p_name, p_locale, p_timezone, 'provisioning',
        app_private.current_actor_id(), p_creation_request_id, p_fingerprint, p_now, p_now, 1
    );
    INSERT INTO public.user_invitations (
        id, organization_id, email, email_normalized, role, invitation_kind, token_hash,
        expires_at, invited_by, delivery_status, created_at, updated_at
    ) VALUES (
        p_invitation_id, p_organization_id, p_email, p_email_normalized, 'admin',
        'initial_administrator', p_token_hash, p_expires_at, app_private.current_actor_id(),
        'pending', p_now, p_now
    );
    INSERT INTO public.invitation_delivery_attempts (
        id, organization_id, invitation_id, request_id, kind, status, requested_by, created_at
    ) VALUES (
        p_delivery_attempt_id, p_organization_id, p_invitation_id, p_creation_request_id,
        'initial', 'pending', app_private.current_actor_id(), p_now
    );
    SELECT pg_catalog.to_jsonb(view) INTO v_view
    FROM app_private.platform_provisioning_view(p_organization_id, p_now) AS view;
    RETURN pg_catalog.jsonb_build_object(
        'code', 'created', 'view', v_view, 'delivery_attempt_id', p_delivery_attempt_id
    );
END
$function$;
ALTER FUNCTION app_private.platform_provision_organization(
    uuid, uuid, uuid, text, text, text, text, text, uuid, text, text,
    timestamp with time zone, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.platform_provision_organization(
    uuid, uuid, uuid, text, text, text, text, text, uuid, text, text,
    timestamp with time zone, timestamp with time zone
) FROM PUBLIC;
"""


_LIST_FUNCTION = """
CREATE FUNCTION app_private.platform_list_organizations(
    p_before_created_at timestamp with time zone,
    p_before_id uuid,
    p_limit integer,
    p_now timestamp with time zone
)
RETURNS TABLE (
    organization_id uuid,
    organization_name text,
    organization_locale text,
    organization_timezone text,
    organization_status text,
    organization_version integer,
    organization_created_at timestamp with time zone,
    organization_activated_at timestamp with time zone,
    invitation_id uuid,
    recipient_email text,
    invitation_role text,
    invitation_state text,
    invitation_delivery_status text,
    invitation_expires_at timestamp with time zone
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
BEGIN
    IF NOT app_private.is_platform_actor() THEN
        RAISE EXCEPTION 'platform capability required' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT view.*
    FROM public.organizations AS organization
    CROSS JOIN LATERAL app_private.platform_provisioning_view(organization.id, p_now) AS view
    WHERE p_before_created_at IS NULL
       OR (organization.created_at, organization.id) < (p_before_created_at, p_before_id)
    ORDER BY organization.created_at DESC, organization.id DESC
    LIMIT p_limit;
END
$function$;
ALTER FUNCTION app_private.platform_list_organizations(
    timestamp with time zone, uuid, integer, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.platform_list_organizations(
    timestamp with time zone, uuid, integer, timestamp with time zone
) FROM PUBLIC;
"""


_RESEND_FUNCTION = """
CREATE FUNCTION app_private.platform_resend_initial_invitation(
    p_organization_id uuid,
    p_invitation_id uuid,
    p_delivery_attempt_id uuid,
    p_request_id uuid,
    p_token_hash text,
    p_expires_at timestamp with time zone,
    p_now timestamp with time zone,
    p_cooldown_seconds integer,
    p_window_seconds integer,
    p_max_per_window integer
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_organization public.organizations%ROWTYPE;
    v_current public.user_invitations%ROWTYPE;
    v_attempt public.invitation_delivery_attempts%ROWTYPE;
    v_last_attempt timestamp with time zone;
    v_resend_count integer;
    v_retry integer;
    v_view jsonb;
BEGIN
    IF NOT app_private.is_platform_actor() THEN
        RAISE EXCEPTION 'platform capability required' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_organization_id::text, 0));

    SELECT * INTO v_attempt
    FROM public.invitation_delivery_attempts
    WHERE request_id = p_request_id;
    IF FOUND THEN
        IF v_attempt.organization_id <> p_organization_id
           OR v_attempt.requested_by <> app_private.current_actor_id() THEN
            RETURN pg_catalog.jsonb_build_object('code', 'idempotency_conflict');
        END IF;
        SELECT pg_catalog.to_jsonb(view) INTO v_view
        FROM app_private.platform_provisioning_view(p_organization_id, p_now) AS view;
        RETURN pg_catalog.jsonb_build_object('code', 'replayed', 'view', v_view);
    END IF;

    SELECT * INTO v_organization
    FROM public.organizations
    WHERE id = p_organization_id
    FOR UPDATE;
    IF NOT FOUND OR v_organization.status <> 'provisioning' THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    SELECT * INTO v_current
    FROM public.user_invitations
    WHERE organization_id = p_organization_id
      AND invitation_kind = 'initial_administrator'
    ORDER BY created_at DESC, id DESC
    LIMIT 1
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    IF v_current.accepted_at IS NOT NULL THEN
        RETURN pg_catalog.jsonb_build_object('code', 'already_accepted');
    END IF;

    SELECT pg_catalog.max(created_at) INTO v_last_attempt
    FROM public.invitation_delivery_attempts
    WHERE organization_id = p_organization_id;
    IF v_last_attempt IS NOT NULL AND v_last_attempt + pg_catalog.make_interval(secs => p_cooldown_seconds) > p_now THEN
        v_retry := CEIL(EXTRACT(EPOCH FROM (
            v_last_attempt + pg_catalog.make_interval(secs => p_cooldown_seconds) - p_now
        )))::integer;
        RETURN pg_catalog.jsonb_build_object('code', 'rate_limited', 'retry_after_seconds', v_retry);
    END IF;
    SELECT pg_catalog.count(*)::integer INTO v_resend_count
    FROM public.invitation_delivery_attempts
    WHERE organization_id = p_organization_id
      AND kind = 'resend'
      AND created_at > p_now - pg_catalog.make_interval(secs => p_window_seconds);
    IF v_resend_count >= p_max_per_window THEN
        RETURN pg_catalog.jsonb_build_object('code', 'rate_limited', 'retry_after_seconds', p_window_seconds);
    END IF;

    UPDATE public.user_invitations
    SET revoked_at = COALESCE(revoked_at, p_now), updated_at = p_now
    WHERE id = v_current.id;
    INSERT INTO public.user_invitations (
        id, organization_id, email, email_normalized, role, invitation_kind, token_hash,
        expires_at, invited_by, supersedes_invitation_id, delivery_status, created_at, updated_at
    ) VALUES (
        p_invitation_id, p_organization_id, v_current.email, v_current.email_normalized,
        v_current.role, v_current.invitation_kind, p_token_hash, p_expires_at,
        app_private.current_actor_id(), v_current.id, 'pending', p_now, p_now
    );
    INSERT INTO public.invitation_delivery_attempts (
        id, organization_id, invitation_id, request_id, kind, status, requested_by, created_at
    ) VALUES (
        p_delivery_attempt_id, p_organization_id, p_invitation_id, p_request_id,
        'resend', 'pending', app_private.current_actor_id(), p_now
    );
    SELECT pg_catalog.to_jsonb(view) INTO v_view
    FROM app_private.platform_provisioning_view(p_organization_id, p_now) AS view;
    RETURN pg_catalog.jsonb_build_object(
        'code', 'created', 'view', v_view, 'delivery_attempt_id', p_delivery_attempt_id
    );
END
$function$;
ALTER FUNCTION app_private.platform_resend_initial_invitation(
    uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone,
    integer, integer, integer
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.platform_resend_initial_invitation(
    uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone,
    integer, integer, integer
) FROM PUBLIC;
"""


_REVOKE_FUNCTION = """
CREATE FUNCTION app_private.platform_revoke_initial_invitation(
    p_organization_id uuid,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_invitation public.user_invitations%ROWTYPE;
    v_view jsonb;
    v_code text;
BEGIN
    IF NOT app_private.is_platform_actor() THEN
        RAISE EXCEPTION 'platform capability required' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_organization_id::text, 0));
    IF NOT EXISTS (SELECT 1 FROM public.organizations WHERE id = p_organization_id) THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    SELECT * INTO v_invitation
    FROM public.user_invitations
    WHERE organization_id = p_organization_id
      AND invitation_kind = 'initial_administrator'
    ORDER BY created_at DESC, id DESC
    LIMIT 1
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    IF v_invitation.accepted_at IS NOT NULL THEN
        RETURN pg_catalog.jsonb_build_object('code', 'already_accepted');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.organizations WHERE id = p_organization_id AND status = 'provisioning'
    ) THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    v_code := CASE WHEN v_invitation.revoked_at IS NULL THEN 'revoked' ELSE 'already_revoked' END;
    UPDATE public.user_invitations
    SET revoked_at = COALESCE(revoked_at, p_now), updated_at = p_now
    WHERE id = v_invitation.id;
    SELECT pg_catalog.to_jsonb(view) INTO v_view
    FROM app_private.platform_provisioning_view(p_organization_id, p_now) AS view;
    RETURN pg_catalog.jsonb_build_object('code', v_code, 'view', v_view);
END
$function$;
ALTER FUNCTION app_private.platform_revoke_initial_invitation(uuid, timestamp with time zone)
    OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.platform_revoke_initial_invitation(uuid, timestamp with time zone) FROM PUBLIC;
"""


_FINALIZE_FUNCTION = """
CREATE FUNCTION app_private.platform_finalize_invitation_delivery(
    p_invitation_id uuid,
    p_delivery_attempt_id uuid,
    p_sent boolean,
    p_failure_code text,
    p_now timestamp with time zone
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_updated integer;
    v_expected_status text := CASE WHEN p_sent THEN 'sent' ELSE 'failed' END;
BEGIN
    IF NOT app_private.is_platform_actor() THEN
        RAISE EXCEPTION 'platform capability required' USING ERRCODE = '42501';
    END IF;
    UPDATE public.invitation_delivery_attempts
    SET status = v_expected_status,
        failure_code = CASE WHEN p_sent THEN NULL ELSE p_failure_code END,
        completed_at = p_now
    WHERE id = p_delivery_attempt_id
      AND invitation_id = p_invitation_id
      AND requested_by = app_private.current_actor_id()
      AND status = 'pending';
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    IF v_updated = 0 THEN
        RETURN EXISTS (
            SELECT 1
            FROM public.invitation_delivery_attempts
            WHERE id = p_delivery_attempt_id
              AND invitation_id = p_invitation_id
              AND requested_by = app_private.current_actor_id()
              AND status = v_expected_status
        );
    END IF;
    UPDATE public.user_invitations
    SET delivery_status = v_expected_status,
        delivery_attempted_at = p_now,
        delivered_at = CASE WHEN p_sent THEN p_now ELSE NULL END,
        updated_at = p_now
    WHERE id = p_invitation_id;
    RETURN FOUND;
END
$function$;
ALTER FUNCTION app_private.platform_finalize_invitation_delivery(
    uuid, uuid, boolean, text, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.platform_finalize_invitation_delivery(
    uuid, uuid, boolean, text, timestamp with time zone
) FROM PUBLIC;
"""


_PREVIEW_FUNCTION = """
CREATE FUNCTION app_private.invitation_preview(
    p_token_hash text,
    p_now timestamp with time zone
)
RETURNS TABLE (
    organization_name text,
    invitation_role text,
    invitation_expires_at timestamp with time zone,
    existing_account boolean
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
    SELECT
        organization.name::text,
        invitation.role::text,
        invitation.expires_at,
        EXISTS (
            SELECT 1 FROM public.users AS candidate
            WHERE candidate.email_normalized = invitation.email_normalized
        )
    FROM public.user_invitations AS invitation
    JOIN public.organizations AS organization ON organization.id = invitation.organization_id
    WHERE invitation.token_hash = p_token_hash
      AND invitation.invitation_kind = 'initial_administrator'
      AND invitation.accepted_at IS NULL
      AND invitation.revoked_at IS NULL
      AND invitation.expires_at > p_now
      AND organization.status = 'provisioning'
$function$;
ALTER FUNCTION app_private.invitation_preview(text, timestamp with time zone) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.invitation_preview(text, timestamp with time zone) FROM PUBLIC;
"""


_ACCEPT_NEW_FUNCTION = """
CREATE FUNCTION app_private.accept_invitation_new_account(
    p_token_hash text,
    p_user_id uuid,
    p_membership_id uuid,
    p_display_name text,
    p_password_hash text,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_invitation public.user_invitations%ROWTYPE;
BEGIN
    SELECT invitation.* INTO v_invitation
    FROM public.user_invitations AS invitation
    JOIN public.organizations AS organization ON organization.id = invitation.organization_id
    WHERE invitation.token_hash = p_token_hash
      AND invitation.invitation_kind = 'initial_administrator'
      AND invitation.role = 'admin'
      AND invitation.accepted_at IS NULL
      AND invitation.revoked_at IS NULL
      AND invitation.expires_at > p_now
      AND organization.status = 'provisioning'
    FOR UPDATE OF invitation, organization;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'invalid');
    END IF;
    IF EXISTS (SELECT 1 FROM public.users WHERE email_normalized = v_invitation.email_normalized) THEN
        RETURN pg_catalog.jsonb_build_object('code', 'existing_account');
    END IF;

    BEGIN
        INSERT INTO public.users (
            id, email, email_normalized, display_name, password_hash, status,
            last_active_organization_id, created_at, updated_at, version
        ) VALUES (
            p_user_id, v_invitation.email, v_invitation.email_normalized, p_display_name,
            p_password_hash, 'active', v_invitation.organization_id, p_now, p_now, 1
        );
        INSERT INTO public.memberships (
            id, organization_id, user_id, role, status, created_by, created_at, updated_at
        ) VALUES (
            p_membership_id, v_invitation.organization_id, p_user_id, 'admin', 'active',
            v_invitation.invited_by, p_now, p_now
        );
        UPDATE public.user_invitations
        SET accepted_at = p_now, accepted_by = p_user_id, updated_at = p_now
        WHERE id = v_invitation.id;
        UPDATE public.organizations
        SET status = 'active', activated_at = p_now, updated_at = p_now, version = version + 1
        WHERE id = v_invitation.organization_id;
    EXCEPTION WHEN unique_violation THEN
        RETURN pg_catalog.jsonb_build_object('code', 'existing_account');
    END;
    RETURN pg_catalog.jsonb_build_object(
        'code', 'accepted', 'user_id', p_user_id, 'user_version', 1,
        'organization_id', v_invitation.organization_id
    );
END
$function$;
ALTER FUNCTION app_private.accept_invitation_new_account(
    text, uuid, uuid, text, text, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.accept_invitation_new_account(
    text, uuid, uuid, text, text, timestamp with time zone
) FROM PUBLIC;
"""


_ACCEPT_EXISTING_FUNCTION = """
CREATE FUNCTION app_private.accept_invitation_existing_account(
    p_token_hash text,
    p_membership_id uuid,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_actor public.users%ROWTYPE;
    v_invitation public.user_invitations%ROWTYPE;
    v_membership_status text;
    v_version integer;
BEGIN
    SELECT * INTO v_actor
    FROM public.users
    WHERE id = app_private.current_actor_id()
    FOR UPDATE;
    IF NOT FOUND OR v_actor.status <> 'active' THEN
        RETURN pg_catalog.jsonb_build_object('code', 'account_mismatch');
    END IF;
    SELECT invitation.* INTO v_invitation
    FROM public.user_invitations AS invitation
    JOIN public.organizations AS organization ON organization.id = invitation.organization_id
    WHERE invitation.token_hash = p_token_hash
      AND invitation.invitation_kind = 'initial_administrator'
      AND invitation.role = 'admin'
      AND invitation.accepted_at IS NULL
      AND invitation.revoked_at IS NULL
      AND invitation.expires_at > p_now
      AND organization.status = 'provisioning'
    FOR UPDATE OF invitation, organization;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'invalid');
    END IF;
    IF v_actor.email_normalized <> v_invitation.email_normalized THEN
        RETURN pg_catalog.jsonb_build_object('code', 'account_mismatch');
    END IF;
    SELECT status INTO v_membership_status
    FROM public.memberships
    WHERE organization_id = v_invitation.organization_id AND user_id = v_actor.id
    FOR UPDATE;
    IF FOUND THEN
        IF v_membership_status = 'disabled' THEN
            RETURN pg_catalog.jsonb_build_object('code', 'membership_reactivation_required');
        END IF;
        RETURN pg_catalog.jsonb_build_object('code', 'invalid');
    END IF;

    INSERT INTO public.memberships (
        id, organization_id, user_id, role, status, created_by, created_at, updated_at
    ) VALUES (
        p_membership_id, v_invitation.organization_id, v_actor.id, 'admin', 'active',
        v_invitation.invited_by, p_now, p_now
    );
    UPDATE public.user_invitations
    SET accepted_at = p_now, accepted_by = v_actor.id, updated_at = p_now
    WHERE id = v_invitation.id;
    UPDATE public.organizations
    SET status = 'active', activated_at = p_now, updated_at = p_now, version = version + 1
    WHERE id = v_invitation.organization_id;
    UPDATE public.users
    SET last_active_organization_id = v_invitation.organization_id,
        updated_at = p_now,
        version = version + 1
    WHERE id = v_actor.id
    RETURNING version INTO v_version;
    RETURN pg_catalog.jsonb_build_object(
        'code', 'accepted', 'user_id', v_actor.id, 'user_version', v_version,
        'organization_id', v_invitation.organization_id
    );
END
$function$;
ALTER FUNCTION app_private.accept_invitation_existing_account(
    text, uuid, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.accept_invitation_existing_account(
    text, uuid, timestamp with time zone
) FROM PUBLIC;
"""


def _grant_permissions() -> None:
    for table_name in (
        "users",
        "organizations",
        "memberships",
        "user_invitations",
        "invitation_delivery_attempts",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table_name} TO prospect_rls_definer")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.invitation_delivery_attempts TO prospect_app")
    for signature in (
        "app_private.platform_provision_organization(uuid, uuid, uuid, text, text, text, text, text, uuid, text, text, timestamp with time zone, timestamp with time zone)",
        "app_private.platform_list_organizations(timestamp with time zone, uuid, integer, timestamp with time zone)",
        "app_private.platform_resend_initial_invitation(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)",
        "app_private.platform_revoke_initial_invitation(uuid, timestamp with time zone)",
        "app_private.platform_finalize_invitation_delivery(uuid, uuid, boolean, text, timestamp with time zone)",
        "app_private.invitation_preview(text, timestamp with time zone)",
        "app_private.accept_invitation_new_account(text, uuid, uuid, text, text, timestamp with time zone)",
        "app_private.accept_invitation_existing_account(text, uuid, timestamp with time zone)",
    ):
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.organizations)
               OR EXISTS (SELECT 1 FROM public.user_invitations)
               OR EXISTS (SELECT 1 FROM public.invitation_delivery_attempts) THEN
                RAISE EXCEPTION
                    'Le downgrade 0004 refuse de supprimer des métadonnées de provisioning utiles.';
            END IF;
        END
        $checks$;
        """
    )
    _drop_functions()
    op.execute("DROP POLICY invitation_delivery_attempts_tenant_isolation ON public.invitation_delivery_attempts")
    op.execute("ALTER TABLE public.invitation_delivery_attempts NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.invitation_delivery_attempts DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_invitation_delivery_attempts_org_kind_created", table_name="invitation_delivery_attempts")
    op.drop_table("invitation_delivery_attempts")

    op.drop_constraint(
        op.f("fk_user_invitations_organization_id_supersedes_invitation_id_user_invitations"),
        "user_invitations",
        type_="foreignkey",
    )
    op.drop_constraint(op.f("uq_user_invitations_organization_id_id"), "user_invitations", type_="unique")
    op.drop_constraint(op.f("fk_user_invitations_accepted_by_users"), "user_invitations", type_="foreignkey")
    op.drop_constraint(op.f("ck_user_invitations_terminal_state_exclusive"), "user_invitations", type_="check")
    op.drop_constraint(op.f("ck_user_invitations_delivery_status_allowed"), "user_invitations", type_="check")
    op.drop_constraint(op.f("ck_user_invitations_invitation_kind_allowed"), "user_invitations", type_="check")
    for column in (
        "updated_at",
        "delivered_at",
        "delivery_attempted_at",
        "supersedes_invitation_id",
        "accepted_by",
        "delivery_status",
        "invitation_kind",
    ):
        op.drop_column("user_invitations", column)

    op.drop_constraint(op.f("uq_memberships_organization_id_id"), "memberships", type_="unique")
    op.alter_column("organizations", "status", server_default=sa.text("'active'"))
    op.drop_constraint(op.f("ck_organizations_activation_state_consistent"), "organizations", type_="check")
    op.drop_constraint(op.f("ck_organizations_status_allowed"), "organizations", type_="check")
    op.create_check_constraint(
        op.f("ck_organizations_status_allowed"),
        "organizations",
        "status IN ('active', 'suspended')",
    )
    op.drop_constraint(op.f("ck_organizations_creation_request_fingerprint_length"), "organizations", type_="check")
    op.drop_constraint(op.f("ck_organizations_creation_idempotency_consistent"), "organizations", type_="check")
    op.drop_constraint(op.f("uq_organizations_creation_request_id"), "organizations", type_="unique")
    op.drop_constraint(op.f("fk_organizations_created_by_users"), "organizations", type_="foreignkey")
    for column in ("activated_at", "creation_request_fingerprint", "creation_request_id", "created_by"):
        op.drop_column("organizations", column)


def _drop_functions() -> None:
    for signature in (
        "app_private.accept_invitation_existing_account(text, uuid, timestamp with time zone)",
        "app_private.accept_invitation_new_account(text, uuid, uuid, text, text, timestamp with time zone)",
        "app_private.invitation_preview(text, timestamp with time zone)",
        "app_private.platform_finalize_invitation_delivery(uuid, uuid, boolean, text, timestamp with time zone)",
        "app_private.platform_revoke_initial_invitation(uuid, timestamp with time zone)",
        "app_private.platform_resend_initial_invitation(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)",
        "app_private.platform_list_organizations(timestamp with time zone, uuid, integer, timestamp with time zone)",
        "app_private.platform_provision_organization(uuid, uuid, uuid, text, text, text, text, text, uuid, text, text, timestamp with time zone, timestamp with time zone)",
        "app_private.platform_provisioning_view(uuid, timestamp with time zone)",
        "app_private.is_platform_actor()",
    ):
        op.execute(f"DROP FUNCTION {signature}")
