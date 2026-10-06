"""Add guarded Automation Playbook lifecycle commands.

Revision ID: 20261005_0037
Revises: 20261005_0036
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261005_0037"
down_revision: str | None = "20261005_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIFECYCLE_SIGNATURE = "(text,text,uuid,integer,uuid,text,text)"
_PREFLIGHT_SIGNATURE = "(text,uuid,uuid,text)"


def upgrade() -> None:
    # A suspension generation is part of the context whose equality makes a
    # Preflight reusable. Preflights created before this revision are therefore
    # safely considered stale by the lifecycle guard.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_private.run_automation_preflight(
          p_playbook_code text, p_membership_id uuid, p_correlation_id uuid, p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_org uuid := app_private.current_organization_id();
          v_actor uuid := app_private.current_actor_id();
          v_existing public.automation_preflights%ROWTYPE;
          v_playbook public.automation_playbooks%ROWTYPE;
          v_version public.automation_playbook_versions%ROWTYPE;
          v_preflight_id uuid := gen_random_uuid();
          v_now timestamptz := clock_timestamp();
          v_fingerprint text;
        BEGIN
          IF p_playbook_code NOT IN ('new_prospect','proposal_pending','forgotten_opportunity')
             OR p_correlation_id IS NULL THEN
            RAISE EXCEPTION 'invalid_contract';
          END IF;
          SELECT * INTO v_existing
          FROM public.automation_preflights
          WHERE organization_id = v_org AND correlation_id = p_correlation_id;
          IF FOUND THEN
            RETURN jsonb_build_object(
              'code','completed','id',v_existing.id,'playbook_code',p_playbook_code,
              'ruleset_version',v_existing.ruleset_version,'state',v_existing.state,
              'correlation_id',v_existing.correlation_id,'subject_count',v_existing.subject_count,
              'green_count',v_existing.green_count,'yellow_count',v_existing.yellow_count,
              'red_count',v_existing.red_count,'to_verify_count',v_existing.to_verify_count,
              'created_at',v_existing.created_at,'updated_at',v_existing.updated_at,
              'expires_at',v_existing.expires_at,'replayed',true
            );
          END IF;
          IF NOT EXISTS (
            SELECT 1
            FROM public.organizations o
            JOIN public.memberships m ON m.organization_id = o.id
            JOIN public.users u ON u.id = m.user_id
            WHERE o.id = v_org AND o.status = 'active' AND m.id = p_membership_id
              AND m.user_id = v_actor AND m.status = 'active' AND u.status = 'active'
          ) THEN
            RETURN jsonb_build_object('code','authorization_revoked');
          END IF;
          SELECT * INTO v_playbook
          FROM public.automation_playbooks
          WHERE organization_id = v_org AND code = p_playbook_code
            AND state IN ('draft','preflight_required','ready')
          FOR UPDATE;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','preflight_not_configured');
          END IF;
          SELECT * INTO v_version
          FROM public.automation_playbook_versions
          WHERE organization_id = v_org AND playbook_id = v_playbook.id
          ORDER BY version_number DESC, created_at DESC, id DESC
          LIMIT 1;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','preflight_not_configured');
          END IF;
          v_fingerprint := encode(
            digest(
              jsonb_build_object(
                'schema_version',1,'playbook_code',v_playbook.code,
                'playbook_id',v_playbook.id,'playbook_version',v_version.version_number,
                'ruleset_version',v_version.ruleset_version,'playbook_version_lock',v_playbook.version,
                'playbook_suspension_generation',v_playbook.suspension_generation,
                'organization_automation_enabled',coalesce((
                  SELECT automation_enabled FROM public.automation_organization_settings WHERE organization_id = v_org
                ),false),
                'organization_suspension_generation',coalesce((
                  SELECT suspension_generation FROM public.automation_organization_settings WHERE organization_id = v_org
                ),0)
              )::text,
              'sha256'
            ),'hex'
          );
          INSERT INTO public.automation_preflights (
            id, organization_id, playbook_version_id, requested_by_membership_id, ruleset_version,
            scope_fingerprint, state, correlation_id, subject_count, green_count, yellow_count,
            red_count, to_verify_count, created_at, updated_at, expires_at
          ) VALUES (
            v_preflight_id, v_org, v_version.id, p_membership_id, v_version.ruleset_version,
            v_fingerprint, 'completed', p_correlation_id, 0, 0, 0, 0, 0,
            v_now, v_now, v_now + interval '15 minutes'
          );
          INSERT INTO public.audit_events (
            id, scope, organization_id, actor_kind, actor_id, action, entity_type, entity_id,
            request_id, correlation_id, source, metadata, schema_version, occurred_at
          ) VALUES (
            gen_random_uuid(), 'tenant', v_org, 'user', v_actor, 'automation.preflight_created',
            'automation_preflight', v_preflight_id, p_request_id, p_correlation_id::text, 'api',
            jsonb_build_object('playbook_code',v_playbook.code,'playbook_version',v_version.version_number,
              'ruleset_version',v_version.ruleset_version,'subject_count',0,'effect_free',true),
            1, v_now
          );
          RETURN jsonb_build_object(
            'code','completed','id',v_preflight_id,'playbook_code',v_playbook.code,
            'ruleset_version',v_version.ruleset_version,'state','completed',
            'correlation_id',p_correlation_id,'subject_count',0,'green_count',0,
            'yellow_count',0,'red_count',0,'to_verify_count',0,'created_at',v_now,
            'updated_at',v_now,'expires_at',v_now + interval '15 minutes','replayed',false
          );
        END $fn$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_private.transition_automation_playbook(
          p_playbook_code text, p_command text, p_membership_id uuid, p_expected_version integer,
          p_correlation_id uuid, p_reason_code text, p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_org uuid := app_private.current_organization_id();
          v_actor uuid := app_private.current_actor_id();
          v_playbook public.automation_playbooks%ROWTYPE;
          v_preflight public.automation_preflights%ROWTYPE;
          v_version public.automation_playbook_versions%ROWTYPE;
          v_now timestamptz := clock_timestamp();
          v_fingerprint text;
          v_action text;
          v_replay jsonb;
        BEGIN
          IF p_playbook_code NOT IN ('new_prospect','proposal_pending','forgotten_opportunity')
             OR p_command NOT IN ('activate','suspend','resume')
             OR p_expected_version < 1 OR p_correlation_id IS NULL THEN
            RAISE EXCEPTION 'invalid_contract';
          END IF;
          IF NOT EXISTS (
            SELECT 1
            FROM public.organizations o
            JOIN public.memberships m ON m.organization_id = o.id
            JOIN public.users u ON u.id = m.user_id
            WHERE o.id = v_org AND o.status = 'active' AND m.id = p_membership_id
              AND m.user_id = v_actor AND m.status = 'active' AND u.status = 'active'
          ) THEN
            RETURN jsonb_build_object('code','authorization_revoked');
          END IF;
          SELECT * INTO v_playbook
          FROM public.automation_playbooks
          WHERE organization_id = v_org AND code = p_playbook_code
          FOR UPDATE;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','playbook_not_found');
          END IF;
          v_action := CASE p_command
            WHEN 'activate' THEN 'automation.playbook_activated'
            WHEN 'suspend' THEN 'automation.playbook_suspended'
            ELSE 'automation.playbook_resume_requires_preflight'
          END;
          SELECT metadata INTO v_replay
          FROM public.audit_events
          WHERE organization_id = v_org AND entity_type = 'automation_playbook'
            AND entity_id = v_playbook.id AND action = v_action
            AND correlation_id = p_correlation_id::text
          ORDER BY occurred_at DESC, id DESC
          LIMIT 1;
          IF FOUND THEN
            RETURN jsonb_build_object(
              'code','completed','playbook_code',v_playbook.code,'command',p_command,
              'state',v_replay->>'result_state',
              'prepare_enabled',coalesce((v_replay->>'prepare_enabled')::boolean,false),
              'suspension_generation',(v_replay->>'suspension_generation')::integer,
              'version',(v_replay->>'version')::integer,
              'correlation_id',p_correlation_id,'replayed',true
            );
          END IF;
          IF v_playbook.version <> p_expected_version THEN
            RETURN jsonb_build_object('code','version_conflict');
          END IF;
          IF p_command = 'activate' THEN
            IF NOT EXISTS (
              SELECT 1 FROM public.automation_organization_settings s
              WHERE s.organization_id = v_org AND s.automation_enabled
            ) THEN
              RETURN jsonb_build_object('code','automation_not_enabled');
            END IF;
            IF v_playbook.state <> 'ready' THEN
              RETURN jsonb_build_object('code','preflight_required');
            END IF;
            SELECT * INTO v_version
            FROM public.automation_playbook_versions
            WHERE organization_id = v_org AND playbook_id = v_playbook.id
            ORDER BY version_number DESC, created_at DESC, id DESC
            LIMIT 1;
            IF NOT FOUND THEN
              RETURN jsonb_build_object('code','preflight_required');
            END IF;
            v_fingerprint := encode(
              digest(
                jsonb_build_object(
                  'schema_version',1,'playbook_code',v_playbook.code,
                  'playbook_id',v_playbook.id,'playbook_version',v_version.version_number,
                  'ruleset_version',v_version.ruleset_version,'playbook_version_lock',v_playbook.version,
                  'playbook_suspension_generation',v_playbook.suspension_generation,
                  'organization_automation_enabled',coalesce((
                    SELECT automation_enabled FROM public.automation_organization_settings WHERE organization_id = v_org
                  ),false),
                  'organization_suspension_generation',coalesce((
                    SELECT suspension_generation FROM public.automation_organization_settings WHERE organization_id = v_org
                  ),0)
                )::text,
                'sha256'
              ),'hex'
            );
            SELECT f.* INTO v_preflight
            FROM public.automation_preflights f
            WHERE f.organization_id = v_org AND f.playbook_version_id = v_version.id
              AND f.state = 'completed' AND f.expires_at > v_now
              AND f.scope_fingerprint = v_fingerprint
            ORDER BY f.created_at DESC, f.id DESC
            LIMIT 1
            FOR UPDATE;
            IF NOT FOUND THEN
              RETURN jsonb_build_object('code','preflight_stale');
            END IF;
            IF v_preflight.subject_count < 1 THEN
              RETURN jsonb_build_object('code','preflight_insufficient');
            END IF;
            UPDATE public.automation_playbooks
            SET state = 'active_prepare', prepare_enabled = true, updated_at = v_now, version = version + 1
            WHERE id = v_playbook.id AND organization_id = v_org
            RETURNING * INTO v_playbook;
          ELSIF p_command = 'suspend' THEN
            IF p_reason_code NOT IN ('operator_request','safety_review','rollback') THEN
              RETURN jsonb_build_object('code','suspension_reason_required');
            END IF;
            IF v_playbook.state = 'retired' THEN
              RETURN jsonb_build_object('code','state_transition_invalid');
            END IF;
            UPDATE public.automation_playbooks
            SET state = 'suspended', prepare_enabled = false,
                suspension_generation = suspension_generation + 1,
                updated_at = v_now, version = version + 1
            WHERE id = v_playbook.id AND organization_id = v_org
            RETURNING * INTO v_playbook;
            UPDATE public.automation_organization_settings
            SET suspension_generation = suspension_generation + 1, updated_at = v_now, version = version + 1
            WHERE organization_id = v_org;
          ELSE
            IF v_playbook.state <> 'suspended' THEN
              RETURN jsonb_build_object('code','state_transition_invalid');
            END IF;
            UPDATE public.automation_playbooks
            SET state = 'preflight_required', prepare_enabled = false, updated_at = v_now, version = version + 1
            WHERE id = v_playbook.id AND organization_id = v_org
            RETURNING * INTO v_playbook;
          END IF;
          INSERT INTO public.audit_events (
            id, scope, organization_id, actor_kind, actor_id, action, entity_type, entity_id,
            request_id, correlation_id, source, metadata, schema_version, occurred_at
          ) VALUES (
            gen_random_uuid(), 'tenant', v_org, 'user', v_actor, v_action,
            'automation_playbook', v_playbook.id, p_request_id, p_correlation_id::text, 'api',
            jsonb_build_object('playbook_code',v_playbook.code,'command',p_command,
              'previous_version',p_expected_version,'version',v_playbook.version,
              'result_state',v_playbook.state,'prepare_enabled',v_playbook.prepare_enabled,
              'suspension_generation',v_playbook.suspension_generation,
              'reason_code',p_reason_code,'effect_free',true),
            1, v_now
          );
          RETURN jsonb_build_object(
            'code','completed','playbook_code',v_playbook.code,'command',p_command,
            'state',v_playbook.state,'prepare_enabled',v_playbook.prepare_enabled,
            'suspension_generation',v_playbook.suspension_generation,
            'version',v_playbook.version,'correlation_id',p_correlation_id,'replayed',false
          );
        END $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION app_private.transition_automation_playbook{_LIFECYCLE_SIGNATURE} FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION app_private.transition_automation_playbook{_LIFECYCLE_SIGNATURE} TO prospect_app"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION app_private.transition_automation_playbook{_LIFECYCLE_SIGNATURE} FROM prospect_app"
    )
    op.execute(f"DROP FUNCTION app_private.transition_automation_playbook{_LIFECYCLE_SIGNATURE}")
    # Restore the AUT-COR-04 fingerprint contract exactly.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_private.run_automation_preflight(
          p_playbook_code text, p_membership_id uuid, p_correlation_id uuid, p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_org uuid := app_private.current_organization_id();
          v_actor uuid := app_private.current_actor_id();
          v_existing public.automation_preflights%ROWTYPE;
          v_playbook public.automation_playbooks%ROWTYPE;
          v_version public.automation_playbook_versions%ROWTYPE;
          v_preflight_id uuid := gen_random_uuid();
          v_now timestamptz := clock_timestamp();
          v_fingerprint text;
        BEGIN
          IF p_playbook_code NOT IN ('new_prospect','proposal_pending','forgotten_opportunity')
             OR p_correlation_id IS NULL THEN RAISE EXCEPTION 'invalid_contract'; END IF;
          SELECT * INTO v_existing FROM public.automation_preflights
          WHERE organization_id = v_org AND correlation_id = p_correlation_id;
          IF FOUND THEN RETURN jsonb_build_object('code','completed','id',v_existing.id,'playbook_code',p_playbook_code,
            'ruleset_version',v_existing.ruleset_version,'state',v_existing.state,'correlation_id',v_existing.correlation_id,
            'subject_count',v_existing.subject_count,'green_count',v_existing.green_count,'yellow_count',v_existing.yellow_count,
            'red_count',v_existing.red_count,'to_verify_count',v_existing.to_verify_count,'created_at',v_existing.created_at,
            'updated_at',v_existing.updated_at,'expires_at',v_existing.expires_at,'replayed',true); END IF;
          IF NOT EXISTS (SELECT 1 FROM public.organizations o JOIN public.memberships m ON m.organization_id = o.id
            JOIN public.users u ON u.id = m.user_id WHERE o.id = v_org AND o.status = 'active' AND m.id = p_membership_id
            AND m.user_id = v_actor AND m.status = 'active' AND u.status = 'active') THEN
            RETURN jsonb_build_object('code','authorization_revoked'); END IF;
          SELECT * INTO v_playbook FROM public.automation_playbooks WHERE organization_id = v_org AND code = p_playbook_code
            AND state IN ('draft','preflight_required','ready') FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','preflight_not_configured'); END IF;
          SELECT * INTO v_version FROM public.automation_playbook_versions WHERE organization_id = v_org AND playbook_id = v_playbook.id
            ORDER BY version_number DESC, created_at DESC, id DESC LIMIT 1;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','preflight_not_configured'); END IF;
          v_fingerprint := encode(digest(jsonb_build_object('schema_version',1,'playbook_code',v_playbook.code,
            'playbook_id',v_playbook.id,'playbook_version',v_version.version_number,'ruleset_version',v_version.ruleset_version,
            'playbook_version_lock',v_playbook.version,'playbook_suspension_generation',v_playbook.suspension_generation,
            'organization_automation_enabled',coalesce((SELECT automation_enabled FROM public.automation_organization_settings
              WHERE organization_id = v_org),false))::text,'sha256'),'hex');
          INSERT INTO public.automation_preflights (id, organization_id, playbook_version_id, requested_by_membership_id,
            ruleset_version, scope_fingerprint, state, correlation_id, subject_count, green_count, yellow_count, red_count,
            to_verify_count, created_at, updated_at, expires_at) VALUES (v_preflight_id, v_org, v_version.id, p_membership_id,
            v_version.ruleset_version, v_fingerprint, 'completed', p_correlation_id, 0, 0, 0, 0, 0, v_now, v_now, v_now + interval '15 minutes');
          INSERT INTO public.audit_events (id, scope, organization_id, actor_kind, actor_id, action, entity_type, entity_id,
            request_id, correlation_id, source, metadata, schema_version, occurred_at) VALUES (gen_random_uuid(), 'tenant', v_org,
            'user', v_actor, 'automation.preflight_created', 'automation_preflight', v_preflight_id, p_request_id,
            p_correlation_id::text, 'api', jsonb_build_object('playbook_code',v_playbook.code,'playbook_version',v_version.version_number,
            'ruleset_version',v_version.ruleset_version,'subject_count',0,'effect_free',true), 1, v_now);
          RETURN jsonb_build_object('code','completed','id',v_preflight_id,'playbook_code',v_playbook.code,
            'ruleset_version',v_version.ruleset_version,'state','completed','correlation_id',p_correlation_id,'subject_count',0,
            'green_count',0,'yellow_count',0,'red_count',0,'to_verify_count',0,'created_at',v_now,'updated_at',v_now,
            'expires_at',v_now + interval '15 minutes','replayed',false);
        END $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION app_private.run_automation_preflight{_PREFLIGHT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_private.run_automation_preflight{_PREFLIGHT_SIGNATURE} TO prospect_app")
