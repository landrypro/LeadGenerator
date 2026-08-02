"""Ajouter les membres, capacités et changements d organisation de 2.3.3.

Revision ID: 20260802_0005
Revises: 20260723_0004
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0005"
down_revision: str | None = "20260723_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("memberships", sa.Column("updated_by", sa.Uuid(), nullable=True))
    op.add_column("memberships", sa.Column("version", sa.Integer(), nullable=True))
    op.execute("UPDATE public.memberships SET updated_by = created_by, version = 1")
    op.alter_column("memberships", "updated_by", nullable=False)
    op.alter_column("memberships", "version", nullable=False, server_default=sa.text("1"))
    op.create_foreign_key(
        op.f("fk_memberships_updated_by_users"),
        "memberships",
        "users",
        ["updated_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(op.f("ck_memberships_version_positive"), "memberships", "version > 0")
    _create_functions()
    _grant_permissions()


def _create_functions() -> None:
    definitions = (
        (_TENANT_IS_ADMIN, "app_private.tenant_is_admin()"),
        (
            _INVITATION_VIEW,
            "app_private.tenant_member_invitation_view(uuid, timestamp with time zone)",
        ),
        (
            _UPDATE_ORGANIZATION,
            "app_private.tenant_update_organization(text, text, text, integer, timestamp with time zone)",
        ),
        (
            _UPDATE_MEMBERSHIP,
            "app_private.tenant_update_membership(uuid, text, text, integer, timestamp with time zone)",
        ),
        (
            _CREATE_INVITATION,
            "app_private.tenant_create_member_invitation(uuid, uuid, text, text, text, uuid, text, timestamp with time zone, timestamp with time zone)",
        ),
        (
            _RESEND_INVITATION,
            "app_private.tenant_resend_member_invitation(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)",
        ),
        (
            _REVOKE_INVITATION,
            "app_private.tenant_revoke_member_invitation(uuid, timestamp with time zone)",
        ),
        (
            _FINALIZE_DELIVERY,
            "app_private.tenant_finalize_member_invitation_delivery(uuid, uuid, boolean, text, timestamp with time zone)",
        ),
        (
            _SWITCH_ORGANIZATION,
            "app_private.switch_active_organization(uuid, timestamp with time zone)",
        ),
        (_PREVIEW_FUNCTION, "app_private.invitation_preview(text, timestamp with time zone)"),
        (
            _ACCEPT_NEW_FUNCTION,
            "app_private.accept_invitation_new_account(text, uuid, uuid, text, text, timestamp with time zone)",
        ),
        (
            _ACCEPT_EXISTING_FUNCTION,
            "app_private.accept_invitation_existing_account(text, uuid, timestamp with time zone)",
        ),
    )
    for definition, signature in definitions:
        _execute_function(definition, signature)


def _execute_function(definition: str, signature: str) -> None:
    create_statement = definition.rsplit("\nALTER FUNCTION", maxsplit=1)[0].strip()
    op.execute(create_statement)
    op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")


def _grant_permissions() -> None:
    signatures = (
        "app_private.tenant_is_admin()",
        "app_private.tenant_member_invitation_view(uuid, timestamp with time zone)",
        "app_private.tenant_update_organization(text, text, text, integer, timestamp with time zone)",
        "app_private.tenant_update_membership(uuid, text, text, integer, timestamp with time zone)",
        "app_private.tenant_create_member_invitation(uuid, uuid, text, text, text, uuid, text, timestamp with time zone, timestamp with time zone)",
        "app_private.tenant_resend_member_invitation(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)",
        "app_private.tenant_revoke_member_invitation(uuid, timestamp with time zone)",
        "app_private.tenant_finalize_member_invitation_delivery(uuid, uuid, boolean, text, timestamp with time zone)",
        "app_private.switch_active_organization(uuid, timestamp with time zone)",
    )
    for signature in signatures:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


_TENANT_IS_ADMIN = """
CREATE OR REPLACE FUNCTION app_private.tenant_is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
    SELECT EXISTS (
        SELECT 1
        FROM public.users AS actor
        JOIN public.memberships AS membership ON membership.user_id = actor.id
        JOIN public.organizations AS organization ON organization.id = membership.organization_id
        WHERE actor.id = app_private.current_actor_id()
          AND actor.status = 'active'
          AND membership.organization_id = app_private.current_organization_id()
          AND membership.role = 'admin'
          AND membership.status = 'active'
          AND organization.status = 'active'
    )
$function$;
ALTER FUNCTION app_private.tenant_is_admin() OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_is_admin() FROM PUBLIC;
"""


_INVITATION_VIEW = """
CREATE OR REPLACE FUNCTION app_private.tenant_member_invitation_view(
    p_invitation_id uuid,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
    SELECT pg_catalog.jsonb_build_object(
        'invitation_id', invitation.id,
        'recipient_email', invitation.email,
        'invitation_role', invitation.role,
        'invitation_state', CASE
            WHEN invitation.accepted_at IS NOT NULL THEN 'accepted'
            WHEN invitation.revoked_at IS NOT NULL THEN 'revoked'
            WHEN invitation.expires_at <= p_now THEN 'expired'
            ELSE 'active'
        END,
        'invitation_delivery_status', invitation.delivery_status,
        'invitation_expires_at', invitation.expires_at,
        'invitation_created_at', invitation.created_at
    )
    FROM public.user_invitations AS invitation
    WHERE invitation.id = p_invitation_id
      AND invitation.organization_id = app_private.current_organization_id()
      AND invitation.invitation_kind = 'member'
$function$;
ALTER FUNCTION app_private.tenant_member_invitation_view(uuid, timestamp with time zone)
    OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_member_invitation_view(uuid, timestamp with time zone) FROM PUBLIC;
"""


_UPDATE_ORGANIZATION = """
CREATE OR REPLACE FUNCTION app_private.tenant_update_organization(
    p_name text,
    p_locale text,
    p_timezone text,
    p_expected_version integer,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_organization public.organizations%ROWTYPE;
BEGIN
    IF NOT app_private.tenant_is_admin() THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    SELECT * INTO v_organization
    FROM public.organizations
    WHERE id = app_private.current_organization_id() AND status = 'active'
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    IF v_organization.version <> p_expected_version THEN
        RETURN pg_catalog.jsonb_build_object(
            'code', 'version_conflict', 'current_version', v_organization.version
        );
    END IF;
    IF COALESCE(p_name, v_organization.name) = v_organization.name
       AND COALESCE(p_locale, v_organization.locale) = v_organization.locale
       AND COALESCE(p_timezone, v_organization.timezone) = v_organization.timezone THEN
        RETURN pg_catalog.jsonb_build_object('code', 'unchanged');
    END IF;
    UPDATE public.organizations
    SET name = COALESCE(p_name, name),
        locale = COALESCE(p_locale, locale),
        timezone = COALESCE(p_timezone, timezone),
        updated_at = p_now,
        version = version + 1
    WHERE id = v_organization.id;
    RETURN pg_catalog.jsonb_build_object('code', 'updated');
END
$function$;
ALTER FUNCTION app_private.tenant_update_organization(
    text, text, text, integer, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_update_organization(
    text, text, text, integer, timestamp with time zone
) FROM PUBLIC;
"""


_UPDATE_MEMBERSHIP = """
CREATE OR REPLACE FUNCTION app_private.tenant_update_membership(
    p_membership_id uuid,
    p_role text,
    p_status text,
    p_expected_version integer,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_organization public.organizations%ROWTYPE;
    v_membership public.memberships%ROWTYPE;
    v_new_role text;
    v_new_status text;
    v_user_version integer;
BEGIN
    IF NOT app_private.tenant_is_admin() THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    SELECT * INTO v_organization
    FROM public.organizations
    WHERE id = app_private.current_organization_id() AND status = 'active'
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    SELECT * INTO v_membership
    FROM public.memberships
    WHERE id = p_membership_id AND organization_id = v_organization.id
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    IF v_membership.version <> p_expected_version THEN
        RETURN pg_catalog.jsonb_build_object(
            'code', 'version_conflict', 'current_version', v_membership.version
        );
    END IF;
    v_new_role := COALESCE(p_role, v_membership.role);
    v_new_status := COALESCE(p_status, v_membership.status);
    IF v_new_role = v_membership.role AND v_new_status = v_membership.status THEN
        RETURN pg_catalog.jsonb_build_object('code', 'unchanged');
    END IF;
    IF v_membership.role = 'admin' AND v_membership.status = 'active'
       AND NOT (v_new_role = 'admin' AND v_new_status = 'active')
       AND NOT EXISTS (
           SELECT 1 FROM public.memberships AS other
           WHERE other.organization_id = v_organization.id
             AND other.id <> v_membership.id
             AND other.role = 'admin' AND other.status = 'active'
       ) THEN
        RETURN pg_catalog.jsonb_build_object('code', 'last_active_administrator');
    END IF;
    UPDATE public.memberships
    SET role = v_new_role,
        status = v_new_status,
        updated_by = app_private.current_actor_id(),
        updated_at = p_now,
        version = version + 1
    WHERE id = v_membership.id;
    UPDATE public.users
    SET updated_at = p_now, version = version + 1
    WHERE id = v_membership.user_id
    RETURNING version INTO v_user_version;
    RETURN pg_catalog.jsonb_build_object(
        'code', 'updated', 'user_version', v_user_version, 'user_id', v_membership.user_id
    );
END
$function$;
ALTER FUNCTION app_private.tenant_update_membership(
    uuid, text, text, integer, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_update_membership(
    uuid, text, text, integer, timestamp with time zone
) FROM PUBLIC;
"""


_CREATE_INVITATION = """
CREATE OR REPLACE FUNCTION app_private.tenant_create_member_invitation(
    p_invitation_id uuid,
    p_delivery_attempt_id uuid,
    p_email text,
    p_email_normalized text,
    p_role text,
    p_request_id uuid,
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
    v_attempt public.invitation_delivery_attempts%ROWTYPE;
    v_existing public.user_invitations%ROWTYPE;
    v_membership_status text;
BEGIN
    IF NOT app_private.tenant_is_admin() THEN
        RETURN pg_catalog.jsonb_build_object('code', 'organization_not_active');
    END IF;
    PERFORM 1 FROM public.organizations
    WHERE id = app_private.current_organization_id() AND status = 'active'
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'organization_not_active');
    END IF;
    SELECT * INTO v_attempt
    FROM public.invitation_delivery_attempts
    WHERE request_id = p_request_id
    FOR UPDATE;
    IF FOUND THEN
        SELECT * INTO v_existing FROM public.user_invitations WHERE id = v_attempt.invitation_id;
        IF v_attempt.organization_id = app_private.current_organization_id()
           AND v_attempt.kind = 'initial'
           AND v_attempt.requested_by = app_private.current_actor_id()
           AND v_existing.invitation_kind = 'member'
           AND v_existing.email_normalized = p_email_normalized
           AND v_existing.role = p_role THEN
            RETURN pg_catalog.jsonb_build_object(
                'code', 'replayed',
                'view', app_private.tenant_member_invitation_view(v_existing.id, p_now)
            );
        END IF;
        RETURN pg_catalog.jsonb_build_object('code', 'idempotency_conflict');
    END IF;
    SELECT membership.status INTO v_membership_status
    FROM public.memberships AS membership
    JOIN public.users AS candidate ON candidate.id = membership.user_id
    WHERE membership.organization_id = app_private.current_organization_id()
      AND candidate.email_normalized = p_email_normalized
    FOR UPDATE OF membership;
    IF FOUND THEN
        IF v_membership_status = 'disabled' THEN
            RETURN pg_catalog.jsonb_build_object('code', 'membership_reactivation_required');
        END IF;
        RETURN pg_catalog.jsonb_build_object('code', 'membership_already_active');
    END IF;
    SELECT * INTO v_existing
    FROM public.user_invitations
    WHERE organization_id = app_private.current_organization_id()
      AND email_normalized = p_email_normalized
      AND accepted_at IS NULL AND revoked_at IS NULL
    FOR UPDATE;
    IF FOUND AND v_existing.expires_at > p_now THEN
        RETURN pg_catalog.jsonb_build_object('code', 'invitation_already_pending');
    END IF;
    IF FOUND THEN
        UPDATE public.user_invitations
        SET revoked_at = p_now, updated_at = p_now
        WHERE id = v_existing.id;
    END IF;
    INSERT INTO public.user_invitations (
        id, organization_id, email, email_normalized, role, invitation_kind,
        token_hash, expires_at, invited_by, delivery_status, created_at, updated_at
    ) VALUES (
        p_invitation_id, app_private.current_organization_id(), p_email, p_email_normalized,
        p_role, 'member', p_token_hash, p_expires_at, app_private.current_actor_id(),
        'pending', p_now, p_now
    );
    INSERT INTO public.invitation_delivery_attempts (
        id, organization_id, invitation_id, request_id, kind, status, requested_by, created_at
    ) VALUES (
        p_delivery_attempt_id, app_private.current_organization_id(), p_invitation_id,
        p_request_id, 'initial', 'pending', app_private.current_actor_id(), p_now
    );
    RETURN pg_catalog.jsonb_build_object(
        'code', 'created', 'delivery_attempt_id', p_delivery_attempt_id,
        'view', app_private.tenant_member_invitation_view(p_invitation_id, p_now)
    );
END
$function$;
ALTER FUNCTION app_private.tenant_create_member_invitation(
    uuid, uuid, text, text, text, uuid, text, timestamp with time zone, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_create_member_invitation(
    uuid, uuid, text, text, text, uuid, text, timestamp with time zone, timestamp with time zone
) FROM PUBLIC;
"""


_RESEND_INVITATION = """
CREATE OR REPLACE FUNCTION app_private.tenant_resend_member_invitation(
    p_invitation_id uuid,
    p_replacement_invitation_id uuid,
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
    v_current public.user_invitations%ROWTYPE;
    v_attempt public.invitation_delivery_attempts%ROWTYPE;
    v_replacement public.user_invitations%ROWTYPE;
    v_last_attempt timestamp with time zone;
    v_count integer;
    v_retry integer;
BEGIN
    IF NOT app_private.tenant_is_admin() THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    PERFORM 1 FROM public.organizations
    WHERE id = app_private.current_organization_id() AND status = 'active'
    FOR UPDATE;
    IF NOT FOUND THEN RETURN pg_catalog.jsonb_build_object('code', 'not_found'); END IF;
    SELECT * INTO v_attempt FROM public.invitation_delivery_attempts
    WHERE request_id = p_request_id FOR UPDATE;
    IF FOUND THEN
        SELECT * INTO v_replacement FROM public.user_invitations WHERE id = v_attempt.invitation_id;
        IF v_attempt.organization_id = app_private.current_organization_id()
           AND v_attempt.kind = 'resend'
           AND v_attempt.requested_by = app_private.current_actor_id()
           AND v_replacement.supersedes_invitation_id = p_invitation_id THEN
            RETURN pg_catalog.jsonb_build_object(
                'code', 'replayed',
                'view', app_private.tenant_member_invitation_view(v_replacement.id, p_now)
            );
        END IF;
        RETURN pg_catalog.jsonb_build_object('code', 'idempotency_conflict');
    END IF;
    SELECT * INTO v_current FROM public.user_invitations
    WHERE id = p_invitation_id
      AND organization_id = app_private.current_organization_id()
      AND invitation_kind = 'member'
    FOR UPDATE;
    IF NOT FOUND OR v_current.revoked_at IS NOT NULL THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    IF v_current.accepted_at IS NOT NULL THEN
        RETURN pg_catalog.jsonb_build_object('code', 'already_accepted');
    END IF;
    WITH RECURSIVE invitation_chain AS (
        SELECT invitation.id, invitation.supersedes_invitation_id
        FROM public.user_invitations AS invitation
        WHERE invitation.id = v_current.id
        UNION ALL
        SELECT previous.id, previous.supersedes_invitation_id
        FROM public.user_invitations AS previous
        JOIN invitation_chain AS current_version
          ON previous.id = current_version.supersedes_invitation_id
    )
    SELECT MAX(attempt.created_at) INTO v_last_attempt
    FROM public.invitation_delivery_attempts AS attempt
    JOIN invitation_chain AS version ON version.id = attempt.invitation_id;
    IF v_last_attempt IS NOT NULL AND v_last_attempt > p_now - pg_catalog.make_interval(secs => p_cooldown_seconds) THEN
        v_retry := GREATEST(1, CEIL(EXTRACT(EPOCH FROM (
            v_last_attempt + pg_catalog.make_interval(secs => p_cooldown_seconds) - p_now
        )))::integer);
        RETURN pg_catalog.jsonb_build_object('code', 'rate_limited', 'retry_after_seconds', v_retry);
    END IF;
    WITH RECURSIVE invitation_chain AS (
        SELECT invitation.id, invitation.supersedes_invitation_id
        FROM public.user_invitations AS invitation
        WHERE invitation.id = v_current.id
        UNION ALL
        SELECT previous.id, previous.supersedes_invitation_id
        FROM public.user_invitations AS previous
        JOIN invitation_chain AS current_version
          ON previous.id = current_version.supersedes_invitation_id
    )
    SELECT COUNT(*) INTO v_count
    FROM public.invitation_delivery_attempts AS attempt
    JOIN invitation_chain AS version ON version.id = attempt.invitation_id
    WHERE attempt.kind = 'resend'
      AND attempt.created_at > p_now - pg_catalog.make_interval(secs => p_window_seconds);
    IF v_count >= p_max_per_window THEN
        RETURN pg_catalog.jsonb_build_object('code', 'rate_limited', 'retry_after_seconds', p_window_seconds);
    END IF;
    UPDATE public.user_invitations SET revoked_at = p_now, updated_at = p_now WHERE id = v_current.id;
    INSERT INTO public.user_invitations (
        id, organization_id, email, email_normalized, role, invitation_kind, token_hash,
        expires_at, invited_by, supersedes_invitation_id, delivery_status, created_at, updated_at
    ) VALUES (
        p_replacement_invitation_id, v_current.organization_id, v_current.email,
        v_current.email_normalized, v_current.role, 'member', p_token_hash, p_expires_at,
        app_private.current_actor_id(), v_current.id, 'pending', p_now, p_now
    );
    INSERT INTO public.invitation_delivery_attempts (
        id, organization_id, invitation_id, request_id, kind, status, requested_by, created_at
    ) VALUES (
        p_delivery_attempt_id, v_current.organization_id, p_replacement_invitation_id,
        p_request_id, 'resend', 'pending', app_private.current_actor_id(), p_now
    );
    RETURN pg_catalog.jsonb_build_object(
        'code', 'created', 'delivery_attempt_id', p_delivery_attempt_id,
        'view', app_private.tenant_member_invitation_view(p_replacement_invitation_id, p_now)
    );
END
$function$;
ALTER FUNCTION app_private.tenant_resend_member_invitation(
    uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone,
    integer, integer, integer
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_resend_member_invitation(
    uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone,
    integer, integer, integer
) FROM PUBLIC;
"""


_REVOKE_INVITATION = """
CREATE OR REPLACE FUNCTION app_private.tenant_revoke_member_invitation(
    p_invitation_id uuid,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE v_invitation public.user_invitations%ROWTYPE;
BEGIN
    IF NOT app_private.tenant_is_admin() THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    SELECT * INTO v_invitation FROM public.user_invitations
    WHERE id = p_invitation_id
      AND organization_id = app_private.current_organization_id()
      AND invitation_kind = 'member'
    FOR UPDATE;
    IF NOT FOUND THEN RETURN pg_catalog.jsonb_build_object('code', 'not_found'); END IF;
    IF v_invitation.accepted_at IS NOT NULL THEN
        RETURN pg_catalog.jsonb_build_object('code', 'already_accepted');
    END IF;
    IF v_invitation.revoked_at IS NOT NULL THEN
        RETURN pg_catalog.jsonb_build_object(
            'code', 'already_revoked',
            'view', app_private.tenant_member_invitation_view(v_invitation.id, p_now)
        );
    END IF;
    UPDATE public.user_invitations SET revoked_at = p_now, updated_at = p_now
    WHERE id = v_invitation.id;
    RETURN pg_catalog.jsonb_build_object(
        'code', 'revoked', 'view', app_private.tenant_member_invitation_view(v_invitation.id, p_now)
    );
END
$function$;
ALTER FUNCTION app_private.tenant_revoke_member_invitation(uuid, timestamp with time zone)
    OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_revoke_member_invitation(uuid, timestamp with time zone) FROM PUBLIC;
"""


_FINALIZE_DELIVERY = """
CREATE OR REPLACE FUNCTION app_private.tenant_finalize_member_invitation_delivery(
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
BEGIN
    UPDATE public.invitation_delivery_attempts
    SET status = CASE WHEN p_sent THEN 'sent' ELSE 'failed' END,
        failure_code = CASE WHEN p_sent THEN NULL ELSE p_failure_code END,
        completed_at = p_now
    WHERE id = p_delivery_attempt_id
      AND invitation_id = p_invitation_id
      AND organization_id = app_private.current_organization_id()
      AND requested_by = app_private.current_actor_id()
      AND status = 'pending';
    IF NOT FOUND THEN RETURN false; END IF;
    UPDATE public.user_invitations
    SET delivery_status = CASE WHEN p_sent THEN 'sent' ELSE 'failed' END,
        delivery_attempted_at = p_now,
        delivered_at = CASE WHEN p_sent THEN p_now ELSE NULL END,
        updated_at = p_now
    WHERE id = p_invitation_id AND organization_id = app_private.current_organization_id();
    RETURN FOUND;
END
$function$;
ALTER FUNCTION app_private.tenant_finalize_member_invitation_delivery(
    uuid, uuid, boolean, text, timestamp with time zone
) OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.tenant_finalize_member_invitation_delivery(
    uuid, uuid, boolean, text, timestamp with time zone
) FROM PUBLIC;
"""


_SWITCH_ORGANIZATION = """
CREATE OR REPLACE FUNCTION app_private.switch_active_organization(
    p_membership_id uuid,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_membership public.memberships%ROWTYPE;
    v_organization_status text;
    v_user_version integer;
BEGIN
    SELECT membership.* INTO v_membership
    FROM public.memberships AS membership
    WHERE membership.id = p_membership_id
      AND membership.user_id = app_private.current_actor_id()
    FOR UPDATE OF membership;
    IF NOT FOUND THEN RETURN pg_catalog.jsonb_build_object('code', 'not_found'); END IF;
    SELECT status INTO v_organization_status
    FROM public.organizations
    WHERE id = v_membership.organization_id
    FOR UPDATE;
    IF v_membership.status <> 'active' OR v_organization_status <> 'active' THEN
        RETURN pg_catalog.jsonb_build_object('code', 'forbidden');
    END IF;
    UPDATE public.users
    SET last_active_organization_id = v_membership.organization_id, updated_at = p_now
    WHERE id = app_private.current_actor_id() AND status = 'active'
    RETURNING version INTO v_user_version;
    IF NOT FOUND THEN RETURN pg_catalog.jsonb_build_object('code', 'forbidden'); END IF;
    RETURN pg_catalog.jsonb_build_object(
        'code', 'switched', 'organization_id', v_membership.organization_id,
        'user_version', v_user_version
    );
END
$function$;
ALTER FUNCTION app_private.switch_active_organization(uuid, timestamp with time zone)
    OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.switch_active_organization(uuid, timestamp with time zone) FROM PUBLIC;
"""


_PREVIEW_FUNCTION = """
CREATE OR REPLACE FUNCTION app_private.invitation_preview(
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
    SELECT organization.name::text, invitation.role::text, invitation.expires_at,
        EXISTS (SELECT 1 FROM public.users AS candidate
                WHERE candidate.email_normalized = invitation.email_normalized)
    FROM public.user_invitations AS invitation
    JOIN public.organizations AS organization ON organization.id = invitation.organization_id
    WHERE invitation.token_hash = p_token_hash
      AND invitation.accepted_at IS NULL AND invitation.revoked_at IS NULL
      AND invitation.expires_at > p_now
      AND ((invitation.invitation_kind = 'initial_administrator'
            AND invitation.role = 'admin' AND organization.status = 'provisioning')
        OR (invitation.invitation_kind = 'member' AND organization.status = 'active'))
$function$;
ALTER FUNCTION app_private.invitation_preview(text, timestamp with time zone)
    OWNER TO prospect_rls_definer;
REVOKE ALL ON FUNCTION app_private.invitation_preview(text, timestamp with time zone) FROM PUBLIC;
"""


_ACCEPT_NEW_FUNCTION = """
CREATE OR REPLACE FUNCTION app_private.accept_invitation_new_account(
    p_token_hash text, p_user_id uuid, p_membership_id uuid, p_display_name text,
    p_password_hash text, p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE v_invitation public.user_invitations%ROWTYPE;
BEGIN
    SELECT invitation.* INTO v_invitation
    FROM public.user_invitations AS invitation
    JOIN public.organizations AS organization ON organization.id = invitation.organization_id
    WHERE invitation.token_hash = p_token_hash
      AND invitation.accepted_at IS NULL AND invitation.revoked_at IS NULL
      AND invitation.expires_at > p_now
      AND ((invitation.invitation_kind = 'initial_administrator'
            AND invitation.role = 'admin' AND organization.status = 'provisioning')
        OR (invitation.invitation_kind = 'member' AND organization.status = 'active'))
    FOR UPDATE OF invitation, organization;
    IF NOT FOUND THEN RETURN pg_catalog.jsonb_build_object('code', 'invalid'); END IF;
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
            id, organization_id, user_id, role, status, created_by, updated_by,
            created_at, updated_at, version
        ) VALUES (
            p_membership_id, v_invitation.organization_id, p_user_id, v_invitation.role,
            'active', v_invitation.invited_by, v_invitation.invited_by, p_now, p_now, 1
        );
        UPDATE public.user_invitations
        SET accepted_at = p_now, accepted_by = p_user_id, updated_at = p_now
        WHERE id = v_invitation.id;
        IF v_invitation.invitation_kind = 'initial_administrator' THEN
            UPDATE public.organizations
            SET status = 'active', activated_at = p_now, updated_at = p_now, version = version + 1
            WHERE id = v_invitation.organization_id;
        END IF;
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
CREATE OR REPLACE FUNCTION app_private.accept_invitation_existing_account(
    p_token_hash text, p_membership_id uuid, p_now timestamp with time zone
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
    SELECT * INTO v_actor FROM public.users
    WHERE id = app_private.current_actor_id() FOR UPDATE;
    IF NOT FOUND OR v_actor.status <> 'active' THEN
        RETURN pg_catalog.jsonb_build_object('code', 'account_mismatch');
    END IF;
    SELECT invitation.* INTO v_invitation
    FROM public.user_invitations AS invitation
    JOIN public.organizations AS organization ON organization.id = invitation.organization_id
    WHERE invitation.token_hash = p_token_hash
      AND invitation.accepted_at IS NULL AND invitation.revoked_at IS NULL
      AND invitation.expires_at > p_now
      AND ((invitation.invitation_kind = 'initial_administrator'
            AND invitation.role = 'admin' AND organization.status = 'provisioning')
        OR (invitation.invitation_kind = 'member' AND organization.status = 'active'))
    FOR UPDATE OF invitation, organization;
    IF NOT FOUND THEN RETURN pg_catalog.jsonb_build_object('code', 'invalid'); END IF;
    IF v_actor.email_normalized <> v_invitation.email_normalized THEN
        RETURN pg_catalog.jsonb_build_object('code', 'account_mismatch');
    END IF;
    SELECT status INTO v_membership_status FROM public.memberships
    WHERE organization_id = v_invitation.organization_id AND user_id = v_actor.id FOR UPDATE;
    IF FOUND THEN
        IF v_membership_status = 'disabled' THEN
            RETURN pg_catalog.jsonb_build_object('code', 'membership_reactivation_required');
        END IF;
        RETURN pg_catalog.jsonb_build_object('code', 'invalid');
    END IF;
    INSERT INTO public.memberships (
        id, organization_id, user_id, role, status, created_by, updated_by,
        created_at, updated_at, version
    ) VALUES (
        p_membership_id, v_invitation.organization_id, v_actor.id, v_invitation.role,
        'active', v_invitation.invited_by, v_invitation.invited_by, p_now, p_now, 1
    );
    UPDATE public.user_invitations SET accepted_at = p_now, accepted_by = v_actor.id, updated_at = p_now
    WHERE id = v_invitation.id;
    IF v_invitation.invitation_kind = 'initial_administrator' THEN
        UPDATE public.organizations
        SET status = 'active', activated_at = p_now, updated_at = p_now, version = version + 1
        WHERE id = v_invitation.organization_id;
    END IF;
    UPDATE public.users
    SET last_active_organization_id = v_invitation.organization_id, updated_at = p_now, version = version + 1
    WHERE id = v_actor.id RETURNING version INTO v_version;
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


def downgrade() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.memberships
                WHERE version <> 1 OR updated_by <> created_by
            ) OR EXISTS (
                SELECT 1 FROM public.user_invitations WHERE invitation_kind = 'member'
            ) THEN
                RAISE EXCEPTION
                    'Le downgrade 0005 refuse de perdre les modifications de membres ou invitations 2.3.3.';
            END IF;
        END
        $checks$;
        """
    )
    for signature in (
        "app_private.switch_active_organization(uuid, timestamp with time zone)",
        "app_private.tenant_finalize_member_invitation_delivery(uuid, uuid, boolean, text, timestamp with time zone)",
        "app_private.tenant_revoke_member_invitation(uuid, timestamp with time zone)",
        "app_private.tenant_resend_member_invitation(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)",
        "app_private.tenant_create_member_invitation(uuid, uuid, text, text, text, uuid, text, timestamp with time zone, timestamp with time zone)",
        "app_private.tenant_update_membership(uuid, text, text, integer, timestamp with time zone)",
        "app_private.tenant_update_organization(text, text, text, integer, timestamp with time zone)",
        "app_private.tenant_member_invitation_view(uuid, timestamp with time zone)",
        "app_private.tenant_is_admin()",
    ):
        op.execute(f"DROP FUNCTION {signature}")
    op.drop_constraint(op.f("ck_memberships_version_positive"), "memberships", type_="check")
    op.drop_constraint(op.f("fk_memberships_updated_by_users"), "memberships", type_="foreignkey")
    op.drop_column("memberships", "version")
    op.drop_column("memberships", "updated_by")
    _execute_function(
        _RESTORE_PREVIEW_FUNCTION,
        "app_private.invitation_preview(text, timestamp with time zone)",
    )
    _execute_function(
        _RESTORE_ACCEPT_NEW_FUNCTION,
        "app_private.accept_invitation_new_account(text, uuid, uuid, text, text, timestamp with time zone)",
    )
    _execute_function(
        _RESTORE_ACCEPT_EXISTING_FUNCTION,
        "app_private.accept_invitation_existing_account(text, uuid, timestamp with time zone)",
    )


_RESTORE_PREVIEW_FUNCTION = _PREVIEW_FUNCTION.replace(
    "      AND ((invitation.invitation_kind = 'initial_administrator'\n"
    "            AND invitation.role = 'admin' AND organization.status = 'provisioning')\n"
    "        OR (invitation.invitation_kind = 'member' AND organization.status = 'active'))",
    "      AND invitation.invitation_kind = 'initial_administrator'\n"
    "      AND invitation.role = 'admin'\n"
    "      AND organization.status = 'provisioning'",
)

_RESTORE_ACCEPT_NEW_FUNCTION = (
    _ACCEPT_NEW_FUNCTION.replace(
        "      AND ((invitation.invitation_kind = 'initial_administrator'\n"
        "            AND invitation.role = 'admin' AND organization.status = 'provisioning')\n"
        "        OR (invitation.invitation_kind = 'member' AND organization.status = 'active'))",
        "      AND invitation.invitation_kind = 'initial_administrator'\n"
        "      AND invitation.role = 'admin'\n"
        "      AND organization.status = 'provisioning'",
    )
    .replace(
        "id, organization_id, user_id, role, status, created_by, updated_by,\n"
        "            created_at, updated_at, version",
        "id, organization_id, user_id, role, status, created_by, created_at, updated_at",
    )
    .replace(
        "p_membership_id, v_invitation.organization_id, p_user_id, v_invitation.role,\n"
        "            'active', v_invitation.invited_by, v_invitation.invited_by, p_now, p_now, 1",
        "p_membership_id, v_invitation.organization_id, p_user_id, 'admin', 'active',\n"
        "            v_invitation.invited_by, p_now, p_now",
    )
)

_RESTORE_ACCEPT_EXISTING_FUNCTION = (
    _ACCEPT_EXISTING_FUNCTION.replace(
        "      AND ((invitation.invitation_kind = 'initial_administrator'\n"
        "            AND invitation.role = 'admin' AND organization.status = 'provisioning')\n"
        "        OR (invitation.invitation_kind = 'member' AND organization.status = 'active'))",
        "      AND invitation.invitation_kind = 'initial_administrator'\n"
        "      AND invitation.role = 'admin'\n"
        "      AND organization.status = 'provisioning'",
    )
    .replace(
        "id, organization_id, user_id, role, status, created_by, updated_by,\n        created_at, updated_at, version",
        "id, organization_id, user_id, role, status, created_by, created_at, updated_at",
    )
    .replace(
        "p_membership_id, v_invitation.organization_id, v_actor.id, v_invitation.role,\n"
        "        'active', v_invitation.invited_by, v_invitation.invited_by, p_now, p_now, 1",
        "p_membership_id, v_invitation.organization_id, v_actor.id, 'admin', 'active',\n"
        "        v_invitation.invited_by, p_now, p_now",
    )
)
