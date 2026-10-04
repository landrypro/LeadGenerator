"""Harden Automation execution guards and audit evidence for IMP-A6.

Revision ID: 20261004_0035
Revises: 20261003_0034
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261004_0035"
down_revision: str | None = "20261003_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREPARE_SIGNATURE = "(uuid,uuid,boolean,text)"
CLOSE_SIGNATURE = "(uuid,text,text)"


def upgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.prepare_automation_new_prospect_task"
        f"{PREPARE_SIGNATURE} FROM prospect_worker"
    )
    op.execute(
        "ALTER FUNCTION app_private.prepare_automation_new_prospect_task"
        f"{PREPARE_SIGNATURE} RENAME TO prepare_automation_new_prospect_task_imp_a4"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.prepare_automation_new_prospect_task_imp_a4"
        f"{PREPARE_SIGNATURE} FROM PUBLIC, prospect_worker"
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.prepare_automation_new_prospect_task(
          p_job_id uuid, p_prospect_id uuid, p_global_enabled boolean, p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          a public.automation_admissions%ROWTYPE;
          v_result jsonb;
          v_reason text;
          v_now timestamptz := clock_timestamp();
        BEGIN
          SELECT a0.* INTO a FROM public.automation_admissions a0
          WHERE a0.job_id=p_job_id AND a0.prospect_id=p_prospect_id
            AND a0.organization_id=app_private.current_organization_id() FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION 'subject_missing'; END IF;

          IF a.state='prepared' AND a.task_id IS NOT NULL THEN
            RETURN app_private.prepare_automation_new_prospect_task_imp_a4(
              p_job_id, p_prospect_id, p_global_enabled, p_request_id
            );
          END IF;
          IF a.state IN ('blocked','rejected','cancelled') THEN
            RETURN jsonb_build_object('result_code','blocked');
          END IF;
          IF a.state IN ('to_verify','quarantined') THEN
            RETURN jsonb_build_object('result_code','to_verify');
          END IF;

          IF EXISTS (
            SELECT 1
            FROM public.automation_playbook_versions newer
            WHERE newer.organization_id=a.organization_id
              AND newer.playbook_id=(
                SELECT current_version.playbook_id
                FROM public.automation_playbook_versions current_version
                WHERE current_version.id=a.playbook_version_id
                  AND current_version.organization_id=a.organization_id
              )
              AND newer.version_number>(
                SELECT current_version.version_number
                FROM public.automation_playbook_versions current_version
                WHERE current_version.id=a.playbook_version_id
                  AND current_version.organization_id=a.organization_id
              )
          ) THEN
            UPDATE public.automation_admissions
            SET state='blocked',result_code='rule_version_stale',completed_at=v_now,updated_at=v_now
            WHERE id=a.id;
            v_result := jsonb_build_object('result_code','blocked');
          ELSE
            v_result := app_private.prepare_automation_new_prospect_task_imp_a4(
              p_job_id, p_prospect_id, p_global_enabled, p_request_id
            );
          END IF;

          IF v_result->>'result_code' IN ('blocked','to_verify') THEN
            SELECT result_code INTO v_reason
            FROM public.automation_admissions WHERE id=a.id;
            INSERT INTO public.audit_events (
              id,scope,organization_id,actor_kind,actor_id,action,entity_type,entity_id,request_id,
              correlation_id,source,metadata,schema_version,occurred_at
            )
            SELECT gen_random_uuid(),'tenant',a.organization_id,'user',j.actor_id,
              CASE WHEN v_result->>'result_code'='to_verify'
                THEN 'automation.execution.to_verify' ELSE 'automation.execution.blocked' END,
              'automation_admission',a.id,p_request_id,a.correlation_id::text,'worker',
              jsonb_build_object('reason_code',coalesce(v_reason,'guard_blocked')),1,v_now
            FROM public.jobs j WHERE j.id=p_job_id
              AND NOT EXISTS (
                SELECT 1 FROM public.audit_events e
                WHERE e.organization_id=a.organization_id
                  AND e.entity_type='automation_admission' AND e.entity_id=a.id
                  AND e.action=CASE WHEN v_result->>'result_code'='to_verify'
                    THEN 'automation.execution.to_verify' ELSE 'automation.execution.blocked' END
              );
          END IF;
          RETURN v_result;
        END $fn$;
        """
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION app_private.prepare_automation_new_prospect_task{PREPARE_SIGNATURE} FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.prepare_automation_new_prospect_task"
        f"{PREPARE_SIGNATURE} TO prospect_worker"
    )

    op.execute(
        r"""
        CREATE FUNCTION app_private.close_automation_admission(
          p_job_id uuid, p_reason_code text, p_request_id text
        ) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          a public.automation_admissions%ROWTYPE;
          v_now timestamptz := clock_timestamp();
          v_action text;
        BEGIN
          IF p_reason_code NOT IN ('authorization_revoked','cancelled') THEN
            RAISE EXCEPTION 'invalid_contract';
          END IF;
          SELECT a0.* INTO a FROM public.automation_admissions a0
          WHERE a0.job_id=p_job_id
            AND a0.organization_id=app_private.current_organization_id() FOR UPDATE;
          IF NOT FOUND THEN RETURN false; END IF;
          IF a.state NOT IN ('accepted','preflight_required','ready_to_prepare') THEN RETURN true; END IF;
          UPDATE public.automation_admissions
          SET state=CASE WHEN p_reason_code='cancelled' THEN 'cancelled' ELSE 'blocked' END,
              result_code=p_reason_code,completed_at=v_now,updated_at=v_now
          WHERE id=a.id;
          v_action := CASE WHEN p_reason_code='cancelled'
            THEN 'automation.execution.cancelled' ELSE 'automation.execution.blocked' END;
          INSERT INTO public.audit_events (
            id,scope,organization_id,actor_kind,actor_id,action,entity_type,entity_id,request_id,
            correlation_id,source,metadata,schema_version,occurred_at
          )
          SELECT gen_random_uuid(),'tenant',a.organization_id,'user',j.actor_id,v_action,
            'automation_admission',a.id,p_request_id,a.correlation_id::text,'worker',
            jsonb_build_object('reason_code',p_reason_code),1,v_now
          FROM public.jobs j WHERE j.id=p_job_id;
          RETURN true;
        END $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION app_private.close_automation_admission{CLOSE_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_private.close_automation_admission{CLOSE_SIGNATURE} TO prospect_worker")


def downgrade() -> None:
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION app_private.close_automation_admission{CLOSE_SIGNATURE} FROM prospect_worker"
    )
    op.execute(f"DROP FUNCTION app_private.close_automation_admission{CLOSE_SIGNATURE}")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.prepare_automation_new_prospect_task"
        f"{PREPARE_SIGNATURE} FROM prospect_worker"
    )
    op.execute(f"DROP FUNCTION app_private.prepare_automation_new_prospect_task{PREPARE_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION app_private.prepare_automation_new_prospect_task_imp_a4"
        f"{PREPARE_SIGNATURE} RENAME TO prepare_automation_new_prospect_task"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.prepare_automation_new_prospect_task"
        f"{PREPARE_SIGNATURE} TO prospect_worker"
    )
