"""Add versioned, auditable Automation exception resolution.

Revision ID: 20261005_0038
Revises: 20261005_0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0038"
down_revision: str | None = "20261005_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SIGNATURE = "(uuid,text,uuid,integer,uuid,text,boolean,text)"


def upgrade() -> None:
    op.add_column(
        "automation_exceptions",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_check_constraint("ck_automation_exceptions_version", "automation_exceptions", "version > 0")
    op.execute(
        """
        CREATE FUNCTION app_private.transition_automation_exception(
          p_exception_id uuid, p_command text, p_membership_id uuid, p_expected_version integer,
          p_correlation_id uuid, p_resolution_code text, p_can_manage_organization boolean, p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_org uuid := app_private.current_organization_id();
          v_actor uuid := app_private.current_actor_id();
          v_exception public.automation_exceptions%ROWTYPE;
          v_now timestamptz := clock_timestamp();
          v_action text;
          v_replay jsonb;
        BEGIN
          IF p_command NOT IN ('claim','resolve','abandon','reconcile')
             OR p_expected_version < 1 OR p_correlation_id IS NULL THEN
            RAISE EXCEPTION 'invalid_contract';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.organizations o
            JOIN public.memberships m ON m.organization_id = o.id
            JOIN public.users u ON u.id = m.user_id
            WHERE o.id = v_org AND o.status = 'active' AND m.id = p_membership_id
              AND m.user_id = v_actor AND m.status = 'active' AND u.status = 'active'
          ) THEN
            RETURN jsonb_build_object('code','authorization_revoked');
          END IF;
          SELECT * INTO v_exception FROM public.automation_exceptions
          WHERE id = p_exception_id AND organization_id = v_org FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','exception_not_found'); END IF;
          v_action := CASE p_command
            WHEN 'claim' THEN 'automation.exception_claimed'
            WHEN 'resolve' THEN 'automation.exception_resolved'
            WHEN 'abandon' THEN 'automation.exception_abandoned'
            ELSE 'automation.exception_reconciled'
          END;
          SELECT metadata INTO v_replay FROM public.audit_events
          WHERE organization_id = v_org AND entity_type = 'automation_exception' AND entity_id = v_exception.id
            AND action = v_action AND correlation_id = p_correlation_id::text
          ORDER BY occurred_at DESC, id DESC LIMIT 1;
          IF FOUND THEN
            RETURN jsonb_build_object('code','completed','id',v_exception.id,'command',p_command,
              'state',v_replay->>'result_state','assigned_membership_id',v_replay->>'assigned_membership_id',
              'resolution_code',v_replay->>'resolution_code','version',(v_replay->>'version')::integer,
              'correlation_id',p_correlation_id,'replayed',true);
          END IF;
          IF v_exception.version <> p_expected_version THEN
            RETURN jsonb_build_object('code','version_conflict');
          END IF;
          IF p_command = 'claim' THEN
            IF v_exception.state <> 'open' OR v_exception.assigned_membership_id IS NOT NULL THEN
              RETURN jsonb_build_object('code','claim_not_available');
            END IF;
            UPDATE public.automation_exceptions
            SET state='in_progress', assigned_membership_id=p_membership_id, updated_at=v_now, version=version+1
            WHERE id=v_exception.id AND organization_id=v_org RETURNING * INTO v_exception;
          ELSE
            IF NOT p_can_manage_organization
               AND v_exception.assigned_membership_id IS DISTINCT FROM p_membership_id THEN
              RETURN jsonb_build_object('code','exception_not_assigned');
            END IF;
            IF v_exception.state <> 'in_progress' THEN
              RETURN jsonb_build_object('code','exception_not_in_progress');
            END IF;
            IF p_command = 'resolve' THEN
              IF p_resolution_code NOT IN ('human_review_complete','canonical_record_confirmed','no_action_required') THEN
                RETURN jsonb_build_object('code','resolution_code_invalid');
              END IF;
              UPDATE public.automation_exceptions
              SET state='resolved', resolution_code=p_resolution_code, updated_at=v_now, version=version+1
              WHERE id=v_exception.id AND organization_id=v_org RETURNING * INTO v_exception;
            ELSIF p_command = 'abandon' THEN
              IF p_resolution_code NOT IN ('not_actionable','duplicate_case','expired_context') THEN
                RETURN jsonb_build_object('code','resolution_code_invalid');
              END IF;
              UPDATE public.automation_exceptions
              SET state='abandoned', resolution_code=p_resolution_code, updated_at=v_now, version=version+1
              WHERE id=v_exception.id AND organization_id=v_org RETURNING * INTO v_exception;
            ELSE
              -- A reconciliation only proves that a correlation was checked. It
              -- never retries a job or creates an object; a human must resolve it.
              UPDATE public.automation_exceptions
              SET updated_at=v_now, version=version+1
              WHERE id=v_exception.id AND organization_id=v_org RETURNING * INTO v_exception;
            END IF;
          END IF;
          INSERT INTO public.audit_events (
            id,scope,organization_id,actor_kind,actor_id,action,entity_type,entity_id,request_id,
            correlation_id,source,metadata,schema_version,occurred_at
          ) VALUES (
            gen_random_uuid(),'tenant',v_org,'user',v_actor,v_action,'automation_exception',v_exception.id,
            p_request_id,p_correlation_id::text,'api',jsonb_build_object(
              'command',p_command,'previous_version',p_expected_version,'version',v_exception.version,
              'result_state',v_exception.state,'assigned_membership_id',v_exception.assigned_membership_id,
              'resolution_code',v_exception.resolution_code,
              'result_code',CASE WHEN p_command='reconcile' THEN 'no_retry' ELSE 'human_decision' END,
              'effect_free',true),1,v_now
          );
          RETURN jsonb_build_object('code','completed','id',v_exception.id,'command',p_command,
            'state',v_exception.state,'assigned_membership_id',v_exception.assigned_membership_id,
            'resolution_code',v_exception.resolution_code,'version',v_exception.version,
            'correlation_id',p_correlation_id,'replayed',false);
        END $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION app_private.transition_automation_exception{_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_private.transition_automation_exception{_SIGNATURE} TO prospect_app")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION app_private.transition_automation_exception{_SIGNATURE} FROM prospect_app")
    op.execute(f"DROP FUNCTION app_private.transition_automation_exception{_SIGNATURE}")
    op.drop_constraint("ck_automation_exceptions_version", "automation_exceptions", type_="check")
    op.drop_column("automation_exceptions", "version")
