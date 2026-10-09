"""Enforce tenant seat reservations for P52-05.

Revision ID: 20261008_0049
Revises: 20261008_0048
Create Date: 2026-10-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261008_0049"
down_revision: str | Sequence[str] | None = "20261008_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.tenant_seat_reservation_decision(
          p_operation text, p_excluded_invitation_id uuid, p_now timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_organization_id uuid := app_private.current_organization_id();
          v_active_decision jsonb;
          v_pending_decision jsonb;
          v_active_limit bigint;
          v_pending_limit bigint;
          v_active_count bigint;
          v_pending_count bigint;
        BEGIN
          IF p_operation NOT IN ('reserve','accept') OR v_organization_id IS NULL THEN
            RETURN jsonb_build_object('code','seat_entitlement_unavailable');
          END IF;
          PERFORM 1 FROM public.organizations
          WHERE id=v_organization_id AND status='active' FOR UPDATE;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','seat_entitlement_unavailable');
          END IF;
          v_active_decision := app_private.tenant_effective_entitlement('seats.active_members.max', p_now);
          v_pending_decision := app_private.tenant_effective_entitlement('seats.pending_invitations.max', p_now);
          -- P5.2 introduit le moteur et ses preuves synthétiques ; l'application
          -- obligatoire à toutes les invitations CRM est planifiée en P5.4.
          -- Les organisations historiques sans contrat gardent donc leur flux
          -- existant, tandis que tout contrat présent reste évalué strictement.
          IF v_active_decision->>'reason' = 'contract_not_active'
             AND v_pending_decision->>'reason' = 'contract_not_active' THEN
            RETURN jsonb_build_object('code','allowed');
          END IF;
          IF v_active_decision->>'code' = 'entitlement_disabled'
             OR v_pending_decision->>'code' = 'entitlement_disabled' THEN
            RETURN jsonb_build_object('code','seat_limit_reached');
          END IF;
          IF v_active_decision->>'code' <> 'allowed' OR v_pending_decision->>'code' <> 'allowed' THEN
            RETURN jsonb_build_object('code','seat_entitlement_unavailable');
          END IF;
          v_active_limit := (v_active_decision->>'integer_value')::bigint;
          v_pending_limit := (v_pending_decision->>'integer_value')::bigint;
          SELECT count(*) INTO v_active_count FROM public.memberships
          WHERE organization_id=v_organization_id AND status='active';
          SELECT count(*) INTO v_pending_count FROM public.user_invitations
          WHERE organization_id=v_organization_id AND invitation_kind='member'
            AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > p_now
            AND (p_excluded_invitation_id IS NULL OR id <> p_excluded_invitation_id);
          IF p_operation = 'reserve' AND (
            v_active_count + v_pending_count >= v_active_limit OR v_pending_count >= v_pending_limit
          ) THEN
            RETURN jsonb_build_object('code','seat_limit_reached');
          END IF;
          IF p_operation = 'accept' AND (
            v_active_count + 1 > v_active_limit
            OR v_active_count + 1 + v_pending_count > v_active_limit
            OR v_pending_count > v_pending_limit
          ) THEN
            RETURN jsonb_build_object('code','seat_limit_reached');
          END IF;
          RETURN jsonb_build_object('code','allowed');
        END $fn$;
        """
    )
    op.execute(
        "ALTER FUNCTION app_private.tenant_seat_reservation_decision(text, uuid, timestamptz) OWNER TO prospect_rls_definer"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.tenant_seat_reservation_decision(text, uuid, timestamptz) FROM PUBLIC"
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.tenant_create_member_invitation(
          p_invitation_id uuid, p_delivery_attempt_id uuid, p_email text, p_email_normalized text,
          p_role text, p_request_id uuid, p_token_hash text, p_expires_at timestamptz, p_now timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_attempt public.invitation_delivery_attempts%ROWTYPE;
          v_existing public.user_invitations%ROWTYPE;
          v_membership_status text;
          v_seat_decision jsonb;
        BEGIN
          IF NOT app_private.tenant_is_admin() THEN RETURN jsonb_build_object('code','organization_not_active'); END IF;
          PERFORM 1 FROM public.organizations WHERE id=app_private.current_organization_id() AND status='active' FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','organization_not_active'); END IF;
          SELECT * INTO v_attempt FROM public.invitation_delivery_attempts WHERE request_id=p_request_id FOR UPDATE;
          IF FOUND THEN
            SELECT * INTO v_existing FROM public.user_invitations WHERE id=v_attempt.invitation_id;
            IF v_attempt.organization_id=app_private.current_organization_id() AND v_attempt.kind='initial'
              AND v_attempt.requested_by=app_private.current_actor_id() AND v_existing.invitation_kind='member'
              AND v_existing.email_normalized=p_email_normalized AND v_existing.role=p_role THEN
              RETURN jsonb_build_object('code','replayed','view',app_private.tenant_member_invitation_view(v_existing.id,p_now));
            END IF;
            RETURN jsonb_build_object('code','idempotency_conflict');
          END IF;
          SELECT membership.status INTO v_membership_status FROM public.memberships AS membership
          JOIN public.users AS candidate ON candidate.id=membership.user_id
          WHERE membership.organization_id=app_private.current_organization_id() AND candidate.email_normalized=p_email_normalized
          FOR UPDATE OF membership;
          IF FOUND THEN
            IF v_membership_status='disabled' THEN RETURN jsonb_build_object('code','membership_reactivation_required'); END IF;
            RETURN jsonb_build_object('code','membership_already_active');
          END IF;
          SELECT * INTO v_existing FROM public.user_invitations
          WHERE organization_id=app_private.current_organization_id() AND email_normalized=p_email_normalized
            AND accepted_at IS NULL AND revoked_at IS NULL FOR UPDATE;
          IF FOUND AND v_existing.expires_at>p_now THEN RETURN jsonb_build_object('code','invitation_already_pending'); END IF;
          v_seat_decision := app_private.tenant_seat_reservation_decision('reserve',NULL,p_now);
          IF v_seat_decision->>'code' <> 'allowed' THEN RETURN v_seat_decision; END IF;
          IF FOUND THEN UPDATE public.user_invitations SET revoked_at=p_now,updated_at=p_now WHERE id=v_existing.id; END IF;
          INSERT INTO public.user_invitations (id,organization_id,email,email_normalized,role,invitation_kind,token_hash,expires_at,invited_by,delivery_status,created_at,updated_at)
          VALUES (p_invitation_id,app_private.current_organization_id(),p_email,p_email_normalized,p_role,'member',p_token_hash,p_expires_at,app_private.current_actor_id(),'pending',p_now,p_now);
          INSERT INTO public.invitation_delivery_attempts (id,organization_id,invitation_id,request_id,kind,status,requested_by,created_at)
          VALUES (p_delivery_attempt_id,app_private.current_organization_id(),p_invitation_id,p_request_id,'initial','pending',app_private.current_actor_id(),p_now);
          RETURN jsonb_build_object('code','created','delivery_attempt_id',p_delivery_attempt_id,'view',app_private.tenant_member_invitation_view(p_invitation_id,p_now));
        END $fn$;
        """
    )
    op.execute(
        "ALTER FUNCTION app_private.tenant_create_member_invitation(uuid,uuid,text,text,text,uuid,text,timestamptz,timestamptz) OWNER TO prospect_rls_definer"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.tenant_create_member_invitation(uuid,uuid,text,text,text,uuid,text,timestamptz,timestamptz) FROM PUBLIC"
    )
    op.execute(
        r"""
        ALTER FUNCTION app_private.tenant_resend_member_invitation(
          uuid, uuid, uuid, uuid, text, timestamptz, timestamptz, integer, integer, integer
        ) RENAME TO tenant_resend_member_invitation_unchecked
        """
    )

    op.execute(
        r"""
        CREATE FUNCTION app_private.tenant_resend_member_invitation(
          p_invitation_id uuid, p_replacement_invitation_id uuid, p_delivery_attempt_id uuid, p_request_id uuid,
          p_token_hash text, p_expires_at timestamptz, p_now timestamptz, p_cooldown_seconds integer,
          p_window_seconds integer, p_max_per_window integer
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_attempt_id uuid; v_invitation_id uuid; v_seat_decision jsonb;
        BEGIN
          IF NOT app_private.tenant_is_admin() THEN
            RETURN app_private.tenant_resend_member_invitation_unchecked(p_invitation_id,p_replacement_invitation_id,p_delivery_attempt_id,p_request_id,p_token_hash,p_expires_at,p_now,p_cooldown_seconds,p_window_seconds,p_max_per_window);
          END IF;
          SELECT id INTO v_attempt_id FROM public.invitation_delivery_attempts WHERE request_id=p_request_id FOR UPDATE;
          IF FOUND THEN
            RETURN app_private.tenant_resend_member_invitation_unchecked(p_invitation_id,p_replacement_invitation_id,p_delivery_attempt_id,p_request_id,p_token_hash,p_expires_at,p_now,p_cooldown_seconds,p_window_seconds,p_max_per_window);
          END IF;
          SELECT id INTO v_invitation_id FROM public.user_invitations
          WHERE id=p_invitation_id AND organization_id=app_private.current_organization_id() AND invitation_kind='member'
            AND accepted_at IS NULL AND revoked_at IS NULL FOR UPDATE;
          IF NOT FOUND THEN
            RETURN app_private.tenant_resend_member_invitation_unchecked(p_invitation_id,p_replacement_invitation_id,p_delivery_attempt_id,p_request_id,p_token_hash,p_expires_at,p_now,p_cooldown_seconds,p_window_seconds,p_max_per_window);
          END IF;
          v_seat_decision := app_private.tenant_seat_reservation_decision('reserve',v_invitation_id,p_now);
          IF v_seat_decision->>'code' <> 'allowed' THEN RETURN v_seat_decision; END IF;
          RETURN app_private.tenant_resend_member_invitation_unchecked(p_invitation_id,p_replacement_invitation_id,p_delivery_attempt_id,p_request_id,p_token_hash,p_expires_at,p_now,p_cooldown_seconds,p_window_seconds,p_max_per_window);
        END $fn$;
        """
    )
    op.execute(
        "ALTER FUNCTION app_private.tenant_resend_member_invitation(uuid,uuid,uuid,uuid,text,timestamptz,timestamptz,integer,integer,integer) OWNER TO prospect_rls_definer"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.tenant_resend_member_invitation(uuid,uuid,uuid,uuid,text,timestamptz,timestamptz,integer,integer,integer) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.tenant_resend_member_invitation(uuid,uuid,uuid,uuid,text,timestamptz,timestamptz,integer,integer,integer) TO prospect_app"
    )
    _replace_acceptance_functions()


def _replace_acceptance_functions() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.accept_invitation_new_account(
          p_token_hash text,p_user_id uuid,p_membership_id uuid,p_display_name text,p_password_hash text,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_invitation public.user_invitations%ROWTYPE; v_seat_decision jsonb;
        BEGIN
          SELECT invitation.* INTO v_invitation FROM public.user_invitations AS invitation
          JOIN public.organizations AS organization ON organization.id=invitation.organization_id
          WHERE invitation.token_hash=p_token_hash AND invitation.accepted_at IS NULL AND invitation.revoked_at IS NULL
            AND invitation.expires_at>p_now AND ((invitation.invitation_kind='initial_administrator' AND invitation.role='admin' AND organization.status='provisioning') OR (invitation.invitation_kind='member' AND organization.status='active'))
          FOR UPDATE OF invitation,organization;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','invalid'); END IF;
          IF EXISTS (SELECT 1 FROM public.users WHERE email_normalized=v_invitation.email_normalized) THEN RETURN jsonb_build_object('code','existing_account'); END IF;
          IF v_invitation.invitation_kind='member' THEN
            PERFORM set_config('app.organization_id',v_invitation.organization_id::text,true);
            v_seat_decision:=app_private.tenant_seat_reservation_decision('accept',v_invitation.id,p_now);
            IF v_seat_decision->>'code'<>'allowed' THEN RETURN v_seat_decision; END IF;
          END IF;
          BEGIN
            INSERT INTO public.users (id,email,email_normalized,display_name,password_hash,status,last_active_organization_id,created_at,updated_at,version)
            VALUES (p_user_id,v_invitation.email,v_invitation.email_normalized,p_display_name,p_password_hash,'active',v_invitation.organization_id,p_now,p_now,1);
            INSERT INTO public.memberships (id,organization_id,user_id,role,status,created_by,updated_by,created_at,updated_at,version)
            VALUES (p_membership_id,v_invitation.organization_id,p_user_id,v_invitation.role,'active',v_invitation.invited_by,v_invitation.invited_by,p_now,p_now,1);
            UPDATE public.user_invitations SET accepted_at=p_now,accepted_by=p_user_id,updated_at=p_now WHERE id=v_invitation.id;
            IF v_invitation.invitation_kind='initial_administrator' THEN UPDATE public.organizations SET status='active',activated_at=p_now,updated_at=p_now,version=version+1 WHERE id=v_invitation.organization_id; END IF;
          EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('code','existing_account'); END;
          RETURN jsonb_build_object('code','accepted','user_id',p_user_id,'user_version',1,'organization_id',v_invitation.organization_id);
        END $fn$;
        """
    )
    op.execute(
        "ALTER FUNCTION app_private.accept_invitation_new_account(text,uuid,uuid,text,text,timestamptz) OWNER TO prospect_rls_definer"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.accept_invitation_new_account(text,uuid,uuid,text,text,timestamptz) FROM PUBLIC"
    )

    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.accept_invitation_existing_account(
          p_token_hash text,p_membership_id uuid,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_actor public.users%ROWTYPE; v_invitation public.user_invitations%ROWTYPE; v_membership_status text; v_version integer; v_seat_decision jsonb;
        BEGIN
          SELECT * INTO v_actor FROM public.users WHERE id=app_private.current_actor_id() FOR UPDATE;
          IF NOT FOUND OR v_actor.status<>'active' THEN RETURN jsonb_build_object('code','account_mismatch'); END IF;
          SELECT invitation.* INTO v_invitation FROM public.user_invitations AS invitation JOIN public.organizations AS organization ON organization.id=invitation.organization_id
          WHERE invitation.token_hash=p_token_hash AND invitation.accepted_at IS NULL AND invitation.revoked_at IS NULL AND invitation.expires_at>p_now
            AND ((invitation.invitation_kind='initial_administrator' AND invitation.role='admin' AND organization.status='provisioning') OR (invitation.invitation_kind='member' AND organization.status='active')) FOR UPDATE OF invitation,organization;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','invalid'); END IF;
          IF v_actor.email_normalized<>v_invitation.email_normalized THEN RETURN jsonb_build_object('code','account_mismatch'); END IF;
          SELECT status INTO v_membership_status FROM public.memberships WHERE organization_id=v_invitation.organization_id AND user_id=v_actor.id FOR UPDATE;
          IF FOUND THEN IF v_membership_status='disabled' THEN RETURN jsonb_build_object('code','membership_reactivation_required'); END IF; RETURN jsonb_build_object('code','invalid'); END IF;
          IF v_invitation.invitation_kind='member' THEN
            PERFORM set_config('app.organization_id',v_invitation.organization_id::text,true);
            v_seat_decision:=app_private.tenant_seat_reservation_decision('accept',v_invitation.id,p_now);
            IF v_seat_decision->>'code'<>'allowed' THEN RETURN v_seat_decision; END IF;
          END IF;
          INSERT INTO public.memberships (id,organization_id,user_id,role,status,created_by,updated_by,created_at,updated_at,version)
          VALUES (p_membership_id,v_invitation.organization_id,v_actor.id,v_invitation.role,'active',v_invitation.invited_by,v_invitation.invited_by,p_now,p_now,1);
          UPDATE public.user_invitations SET accepted_at=p_now,accepted_by=v_actor.id,updated_at=p_now WHERE id=v_invitation.id;
          IF v_invitation.invitation_kind='initial_administrator' THEN UPDATE public.organizations SET status='active',activated_at=p_now,updated_at=p_now,version=version+1 WHERE id=v_invitation.organization_id; END IF;
          UPDATE public.users SET last_active_organization_id=v_invitation.organization_id,updated_at=p_now,version=version+1 WHERE id=v_actor.id RETURNING version INTO v_version;
          RETURN jsonb_build_object('code','accepted','user_id',v_actor.id,'user_version',v_version,'organization_id',v_invitation.organization_id);
        END $fn$;
        """
    )
    op.execute(
        "ALTER FUNCTION app_private.accept_invitation_existing_account(text,uuid,timestamptz) OWNER TO prospect_rls_definer"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.accept_invitation_existing_account(text,uuid,timestamptz) FROM PUBLIC"
    )


def downgrade() -> None:
    # Les signatures historiques demeurent actives; le helper devient permissif
    # afin qu'un rollback applicatif désactive P52-05 sans briser les invitations.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_private.tenant_seat_reservation_decision(
          p_operation text, p_excluded_invitation_id uuid, p_now timestamptz
        ) RETURNS jsonb LANGUAGE sql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$ SELECT jsonb_build_object('code','allowed') $$
        """
    )
    op.execute(
        "ALTER FUNCTION app_private.tenant_seat_reservation_decision(text, uuid, timestamptz) OWNER TO prospect_rls_definer"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.tenant_seat_reservation_decision(text, uuid, timestamptz) FROM PUBLIC"
    )
    op.execute(
        """
        DROP FUNCTION app_private.tenant_resend_member_invitation(
          uuid, uuid, uuid, uuid, text, timestamptz, timestamptz, integer, integer, integer
        )
        """
    )
    op.execute(
        """
        ALTER FUNCTION app_private.tenant_resend_member_invitation_unchecked(
          uuid, uuid, uuid, uuid, text, timestamptz, timestamptz, integer, integer, integer
        ) RENAME TO tenant_resend_member_invitation
        """
    )
