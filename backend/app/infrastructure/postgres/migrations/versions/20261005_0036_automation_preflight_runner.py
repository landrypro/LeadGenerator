"""Add an effect-free persisted Automation Preflight command.

Revision ID: 20261005_0036
Revises: 20261004_0035
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261005_0036"
down_revision: str | None = "20261004_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SIGNATURE = "(text,uuid,uuid,text)"


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA app_private TO prospect_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.current_organization_id() TO prospect_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.current_actor_id() TO prospect_app")
    op.execute(
        """
        CREATE FUNCTION app_private.run_automation_preflight(
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
                ),false)
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
    op.execute(f"REVOKE ALL ON FUNCTION app_private.run_automation_preflight{_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_private.run_automation_preflight{_SIGNATURE} TO prospect_app")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION app_private.run_automation_preflight{_SIGNATURE} FROM prospect_app")
    op.execute(f"DROP FUNCTION app_private.run_automation_preflight{_SIGNATURE}")
