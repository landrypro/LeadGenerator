"""Ajouter les contrats de mutation atomiques nécessaires à l audit 2.4.2.

Revision ID: 20260809_0007
Revises: 20260809_0006
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_0007"
down_revision: str | None = "20260809_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_FUNCTIONS = {
    "app_private.tenant_update_organization_audited(text, text, text, integer, timestamp with time zone)": r"""
CREATE FUNCTION app_private.tenant_update_organization_audited(
 p_name text, p_locale text, p_timezone text, p_expected_version integer, p_now timestamptz) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_old public.organizations%ROWTYPE; v_result jsonb; v_fields jsonb := '[]'::jsonb;
BEGIN
 SELECT * INTO v_old FROM public.organizations
 WHERE id = app_private.current_organization_id() FOR UPDATE;
 v_result := app_private.tenant_update_organization(p_name,p_locale,p_timezone,p_expected_version,p_now);
 IF v_result->>'code' = 'updated' THEN
  IF p_name IS NOT NULL AND p_name <> v_old.name THEN v_fields := v_fields || '"name"'::jsonb; END IF;
  IF p_locale IS NOT NULL AND p_locale <> v_old.locale THEN v_fields := v_fields || '"locale"'::jsonb; END IF;
  IF p_timezone IS NOT NULL AND p_timezone <> v_old.timezone THEN v_fields := v_fields || '"timezone"'::jsonb; END IF;
  v_result := v_result || jsonb_build_object('changed_fields', v_fields);
 END IF;
 RETURN v_result;
END $f$;
""",
    "app_private.tenant_update_membership_audited(uuid, text, text, integer, timestamp with time zone)": r"""
CREATE FUNCTION app_private.tenant_update_membership_audited(
 p_membership_id uuid, p_role text, p_status text, p_expected_version integer, p_now timestamptz) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_old public.memberships%ROWTYPE; v_result jsonb;
BEGIN
 SELECT * INTO v_old FROM public.memberships WHERE id=p_membership_id
 AND organization_id=app_private.current_organization_id() FOR UPDATE;
 v_result := app_private.tenant_update_membership(p_membership_id,p_role,p_status,p_expected_version,p_now);
 IF v_result->>'code' = 'updated' THEN
  v_result := v_result || jsonb_build_object('previous_role',v_old.role,'previous_status',v_old.status);
 END IF;
 RETURN v_result;
END $f$;
""",
    "app_private.tenant_create_member_invitation_audited(uuid, uuid, text, text, text, uuid, text, timestamp with time zone, timestamp with time zone)": r"""
CREATE FUNCTION app_private.tenant_create_member_invitation_audited(
 p_invitation_id uuid,p_delivery_attempt_id uuid,p_email text,p_email_normalized text,p_role text,
 p_request_id uuid,p_token_hash text,p_expires_at timestamptz,p_now timestamptz) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_old_id uuid; v_result jsonb;
BEGIN
 SELECT id INTO v_old_id FROM public.user_invitations
 WHERE organization_id=app_private.current_organization_id() AND email_normalized=p_email_normalized
 AND accepted_at IS NULL AND revoked_at IS NULL FOR UPDATE;
 v_result := app_private.tenant_create_member_invitation(
  p_invitation_id,p_delivery_attempt_id,p_email,p_email_normalized,p_role,p_request_id,p_token_hash,p_expires_at,p_now);
 IF v_result->>'code'='created' AND v_old_id IS NOT NULL THEN
  v_result := v_result || jsonb_build_object('revoked_invitation_id',v_old_id);
 END IF;
 RETURN v_result;
END $f$;
""",
    "app_private.tenant_resend_member_invitation_audited(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)": r"""
CREATE FUNCTION app_private.tenant_resend_member_invitation_audited(
 p_invitation_id uuid,p_replacement_invitation_id uuid,p_delivery_attempt_id uuid,p_request_id uuid,
 p_token_hash text,p_expires_at timestamptz,p_now timestamptz,p_cooldown_seconds integer,
 p_window_seconds integer,p_max_per_window integer) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_result jsonb;
BEGIN
 v_result := app_private.tenant_resend_member_invitation(p_invitation_id,p_replacement_invitation_id,
  p_delivery_attempt_id,p_request_id,p_token_hash,p_expires_at,p_now,p_cooldown_seconds,p_window_seconds,p_max_per_window);
 IF v_result->>'code'='created' THEN
  v_result := v_result || jsonb_build_object('revoked_invitation_id',p_invitation_id);
 END IF;
 RETURN v_result;
END $f$;
""",
    "app_private.tenant_finalize_member_invitation_delivery_audited(uuid, uuid, boolean, text, timestamp with time zone)": r"""
CREATE FUNCTION app_private.tenant_finalize_member_invitation_delivery_audited(
 p_invitation_id uuid,p_delivery_attempt_id uuid,p_sent boolean,p_failure_code text,p_now timestamptz) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_kind text; v_status text; v_failure_code text; v_transitioned boolean;
 v_expected_status text := CASE WHEN p_sent THEN 'sent' ELSE 'failed' END;
BEGIN
 SELECT kind,status,failure_code INTO v_kind,v_status,v_failure_code
 FROM public.invitation_delivery_attempts WHERE id=p_delivery_attempt_id
 AND invitation_id=p_invitation_id AND organization_id=app_private.current_organization_id()
 AND requested_by=app_private.current_actor_id() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'delivery attempt not found' USING ERRCODE='P0002'; END IF;
 IF v_status <> 'pending' THEN
  IF v_status = v_expected_status
     AND (p_sent OR v_failure_code IS NOT DISTINCT FROM p_failure_code) THEN
   RETURN jsonb_build_object('transitioned',false,'invitation_id',p_invitation_id,
    'delivery_status',v_status,'delivery_kind',v_kind);
  END IF;
  RAISE EXCEPTION 'delivery finalization conflict' USING ERRCODE='23514';
 END IF;
 v_transitioned := app_private.tenant_finalize_member_invitation_delivery(
  p_invitation_id,p_delivery_attempt_id,p_sent,p_failure_code,p_now);
 IF NOT v_transitioned THEN RAISE EXCEPTION 'delivery finalization failed' USING ERRCODE='P0001'; END IF;
 RETURN jsonb_build_object('transitioned',v_transitioned,'invitation_id',p_invitation_id,
  'delivery_status',CASE WHEN p_sent THEN 'sent' ELSE 'failed' END,'delivery_kind',COALESCE(v_kind,'initial'));
END $f$;
""",
    "app_private.switch_active_organization_audited(uuid, timestamp with time zone)": r"""
CREATE FUNCTION app_private.switch_active_organization_audited(p_membership_id uuid,p_now timestamptz) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_previous uuid; v_result jsonb;
BEGIN
 SELECT membership.id INTO v_previous FROM public.users AS candidate
 LEFT JOIN public.memberships AS membership ON membership.user_id=candidate.id
  AND membership.organization_id=candidate.last_active_organization_id
 WHERE candidate.id=app_private.current_actor_id() FOR UPDATE OF candidate;
 v_result := app_private.switch_active_organization(p_membership_id,p_now);
 IF v_result->>'code'='switched' THEN
  v_result := v_result || jsonb_build_object('previous_membership_id',v_previous,'new_membership_id',p_membership_id);
 END IF;
 RETURN v_result;
END $f$;
""",
    "app_private.platform_resend_initial_invitation_audited(uuid, uuid, uuid, uuid, text, timestamp with time zone, timestamp with time zone, integer, integer, integer)": r"""
CREATE FUNCTION app_private.platform_resend_initial_invitation_audited(
 p_organization_id uuid,p_invitation_id uuid,p_delivery_attempt_id uuid,p_request_id uuid,p_token_hash text,
 p_expires_at timestamptz,p_now timestamptz,p_cooldown_seconds integer,p_window_seconds integer,p_max_per_window integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_old_id uuid; v_result jsonb;
BEGIN
 SELECT id INTO v_old_id FROM public.user_invitations WHERE organization_id=p_organization_id
 AND invitation_kind='initial_administrator' AND accepted_at IS NULL AND revoked_at IS NULL
 ORDER BY created_at DESC LIMIT 1 FOR UPDATE;
 v_result := app_private.platform_resend_initial_invitation(p_organization_id,p_invitation_id,p_delivery_attempt_id,
  p_request_id,p_token_hash,p_expires_at,p_now,p_cooldown_seconds,p_window_seconds,p_max_per_window);
 IF v_result->>'code'='created' THEN v_result:=v_result||jsonb_build_object('revoked_invitation_id',v_old_id); END IF;
 RETURN v_result;
END $f$;
""",
    "app_private.platform_finalize_invitation_delivery_audited(uuid, uuid, boolean, text, timestamp with time zone)": r"""
CREATE FUNCTION app_private.platform_finalize_invitation_delivery_audited(
 p_invitation_id uuid,p_delivery_attempt_id uuid,p_sent boolean,p_failure_code text,p_now timestamptz) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_kind text; v_status text; v_failure_code text; v_transitioned boolean;
 v_expected_status text := CASE WHEN p_sent THEN 'sent' ELSE 'failed' END;
BEGIN
 IF NOT app_private.is_platform_actor() THEN
  RAISE EXCEPTION 'platform capability required' USING ERRCODE='42501';
 END IF;
 SELECT kind,status,failure_code INTO v_kind,v_status,v_failure_code
 FROM public.invitation_delivery_attempts WHERE id=p_delivery_attempt_id
 AND invitation_id=p_invitation_id AND requested_by=app_private.current_actor_id() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'delivery attempt not found' USING ERRCODE='P0002'; END IF;
 IF v_status <> 'pending' THEN
  IF v_status = v_expected_status
     AND (p_sent OR v_failure_code IS NOT DISTINCT FROM p_failure_code) THEN
   RETURN jsonb_build_object('transitioned',false,'invitation_id',p_invitation_id,
    'delivery_status',v_status,'delivery_kind',v_kind);
  END IF;
  RAISE EXCEPTION 'delivery finalization conflict' USING ERRCODE='23514';
 END IF;
 v_transitioned := app_private.platform_finalize_invitation_delivery(
  p_invitation_id,p_delivery_attempt_id,p_sent,p_failure_code,p_now);
 IF NOT v_transitioned THEN RAISE EXCEPTION 'delivery finalization failed' USING ERRCODE='P0001'; END IF;
 RETURN jsonb_build_object('transitioned',v_transitioned,'invitation_id',p_invitation_id,
  'delivery_status',CASE WHEN p_sent THEN 'sent' ELSE 'failed' END,'delivery_kind',COALESCE(v_kind,'initial'));
END $f$;
""",
    "app_private.accept_invitation_new_account_audited(text, uuid, uuid, text, text, timestamp with time zone)": r"""
CREATE FUNCTION app_private.accept_invitation_new_account_audited(
 p_token_hash text,p_user_id uuid,p_membership_id uuid,p_display_name text,p_password_hash text,p_now timestamptz)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_invitation public.user_invitations%ROWTYPE; v_result jsonb;
BEGIN
 SELECT * INTO v_invitation FROM public.user_invitations WHERE token_hash=p_token_hash FOR UPDATE;
 v_result:=app_private.accept_invitation_new_account(p_token_hash,p_user_id,p_membership_id,p_display_name,p_password_hash,p_now);
 IF v_result->>'code'='accepted' THEN v_result:=v_result||jsonb_build_object(
  'invitation_id',v_invitation.id,'invitation_kind',v_invitation.invitation_kind,
  'organization_activated',v_invitation.invitation_kind='initial_administrator'); END IF;
 RETURN v_result;
END $f$;
""",
    "app_private.accept_invitation_existing_account_audited(text, uuid, timestamp with time zone)": r"""
CREATE FUNCTION app_private.accept_invitation_existing_account_audited(
 p_token_hash text,p_membership_id uuid,p_now timestamptz) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $f$
DECLARE v_invitation public.user_invitations%ROWTYPE; v_result jsonb;
BEGIN
 SELECT * INTO v_invitation FROM public.user_invitations WHERE token_hash=p_token_hash FOR UPDATE;
 v_result:=app_private.accept_invitation_existing_account(p_token_hash,p_membership_id,p_now);
 IF v_result->>'code'='accepted' THEN v_result:=v_result||jsonb_build_object(
  'invitation_id',v_invitation.id,'invitation_kind',v_invitation.invitation_kind,
  'organization_activated',v_invitation.invitation_kind='initial_administrator'); END IF;
 RETURN v_result;
END $f$;
""",
}


def upgrade() -> None:
    # Les politiques RLS d'audit évaluent directement l'acteur courant sous
    # prospect_app; la fonction de contexte ne révèle que la valeur de session.
    op.execute("GRANT EXECUTE ON FUNCTION app_private.current_actor_id() TO prospect_app")
    for signature, definition in _FUNCTIONS.items():
        op.execute(definition)
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    for signature in reversed(tuple(_FUNCTIONS)):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("REVOKE EXECUTE ON FUNCTION app_private.current_actor_id() FROM prospect_app")
