"""Add bounded API admission and worker effect commands for IMP-A4.

Revision ID: 20261003_0034
Revises: 20261002_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0034"
down_revision: str | None = "20261002_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Les admissions IMP-A3 éventuellement présentes sont consultables mais ne
    # sont pas exécutables sans responsable explicite. Les nouvelles admissions
    # IMP-A4 renseignent toujours cette colonne via la commande bornée.
    op.add_column("automation_admissions", sa.Column("assigned_membership_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_automation_admissions_org_assignee",
        "automation_admissions",
        "memberships",
        ["organization_id", "assigned_membership_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_automation_admissions_org_job",
        "automation_admissions",
        ["organization_id", "job_id"],
        unique=True,
        postgresql_where=sa.text("job_id IS NOT NULL"),
    )
    op.execute("GRANT USAGE ON SCHEMA app_private TO prospect_app, prospect_worker")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.current_organization_id() TO prospect_app, prospect_worker")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.current_actor_id() TO prospect_app, prospect_worker")
    op.execute("GRANT SELECT, UPDATE ON public.automation_admissions TO prospect_worker")
    op.execute("""
        CREATE POLICY automation_admissions_worker_runtime ON public.automation_admissions FOR ALL TO prospect_worker
        USING (organization_id = app_private.current_organization_id())
        WITH CHECK (organization_id = app_private.current_organization_id())
    """)

    op.execute("""
        CREATE FUNCTION app_private.admit_manual_new_prospect_automation(
          p_alias text, p_membership_id uuid, p_assigned_membership_id uuid,
          p_admission_digest text, p_fingerprint text, p_job_digest text,
          p_correlation_id uuid, p_global_enabled boolean, p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_org uuid := app_private.current_organization_id();
          v_actor uuid := app_private.current_actor_id();
          v_existing public.automation_admissions%ROWTYPE;
          v_playbook public.automation_playbooks%ROWTYPE;
          v_version public.automation_playbook_versions%ROWTYPE;
          v_prospect_id uuid; v_preflight_id uuid := gen_random_uuid(); v_decision_id uuid := gen_random_uuid();
          v_admission_id uuid := gen_random_uuid(); v_job_id uuid := gen_random_uuid(); v_now timestamptz := clock_timestamp();
        BEGIN
          IF NOT p_global_enabled THEN RETURN jsonb_build_object('code','automation_disabled'); END IF;
          IF char_length(btrim(p_alias)) NOT BETWEEN 1 AND 160 OR p_admission_digest !~ '^[a-f0-9]{64}$'
             OR p_fingerprint !~ '^[a-f0-9]{64}$' OR p_job_digest !~ '^[a-f0-9]{64}$' THEN
            RAISE EXCEPTION 'invalid_contract';
          END IF;
          SELECT * INTO v_existing FROM public.automation_admissions
          WHERE organization_id = v_org AND idempotency_key_digest = p_admission_digest;
          IF FOUND THEN
            IF v_existing.request_fingerprint <> p_fingerprint THEN
              RETURN jsonb_build_object('code','idempotency_conflict');
            END IF;
            RETURN jsonb_build_object('code','accepted','prospect_id',v_existing.prospect_id,
              'admission_id',v_existing.id,'job_id',v_existing.job_id,'state',v_existing.state,'replayed',true);
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.organizations o JOIN public.memberships m ON m.organization_id=o.id
            JOIN public.users u ON u.id=m.user_id
            WHERE o.id=v_org AND o.status='active' AND m.id=p_membership_id AND m.user_id=v_actor
              AND m.status='active' AND u.status='active'
          ) THEN RETURN jsonb_build_object('code','authorization_revoked'); END IF;
          IF NOT EXISTS (SELECT 1 FROM public.automation_organization_settings s
                         WHERE s.organization_id=v_org AND s.automation_enabled) THEN
            RETURN jsonb_build_object('code','automation_disabled');
          END IF;
          SELECT * INTO v_playbook FROM public.automation_playbooks
          WHERE organization_id=v_org AND code='new_prospect' AND state='active_prepare' AND prepare_enabled;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','automation_disabled'); END IF;
          SELECT * INTO v_version FROM public.automation_playbook_versions
          WHERE organization_id=v_org AND playbook_id=v_playbook.id ORDER BY version_number DESC LIMIT 1;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','automation_disabled'); END IF;
          IF NOT EXISTS (SELECT 1 FROM public.memberships WHERE id=p_assigned_membership_id
                         AND organization_id=v_org AND status='active') THEN
            RETURN jsonb_build_object('code','owner_unavailable');
          END IF;
          IF (SELECT queued_count FROM public.job_scheduler_state WHERE organization_id=v_org) >= 100 THEN
            RETURN jsonb_build_object('code','queue_full');
          END IF;
          INSERT INTO public.prospects (id,organization_id,internal_alias,origin,source_label,stage_code,priority,created_at,updated_at)
          VALUES (gen_random_uuid(),v_org,btrim(p_alias),'manual','manual:user_entry','new',0,v_now,v_now)
          RETURNING id INTO v_prospect_id;
          INSERT INTO public.automation_preflights (
            id,organization_id,playbook_version_id,requested_by_membership_id,ruleset_version,scope_fingerprint,state,
            correlation_id,subject_count,green_count,yellow_count,red_count,to_verify_count,created_at,updated_at,expires_at
          ) VALUES (v_preflight_id,v_org,v_version.id,p_membership_id,v_version.ruleset_version,p_fingerprint,'completed',
            p_correlation_id,1,1,0,0,0,v_now,v_now,v_now + interval '15 minutes');
          INSERT INTO public.automation_decisions (
            id,organization_id,preflight_id,playbook_version_id,subject_type,subject_id,fire_level,next_action,reason_codes,
            context_fingerprint,correlation_id,outcome,created_at,expires_at
          ) VALUES (v_decision_id,v_org,v_preflight_id,v_version.id,'prospect',v_prospect_id,'green','prepare','["ready"]'::jsonb,
            p_fingerprint,p_correlation_id,'prepared',v_now,v_now + interval '15 minutes');
          INSERT INTO public.jobs (id,organization_id,type,schema_version,subject_type,subject_id,actor_id,actor_membership_id,
            idempotency_key_digest,idempotency_key_version,request_fingerprint,status,created_at,available_at)
          VALUES (v_job_id,v_org,'automation_new_prospect_prepare',1,'prospect',v_prospect_id,v_actor,p_membership_id,
            p_job_digest,1,p_fingerprint,'queued',v_now,v_now);
          INSERT INTO public.job_scheduler_state (organization_id,queued_count) VALUES (v_org,1)
          ON CONFLICT (organization_id) DO UPDATE SET queued_count=public.job_scheduler_state.queued_count+1;
          INSERT INTO public.job_events (id,job_id,organization_id,new_status,reason_code,actor_id,created_at)
          VALUES (gen_random_uuid(),v_job_id,v_org,'queued','admitted',v_actor,v_now);
          INSERT INTO public.automation_admissions (
            id,organization_id,prospect_id,playbook_version_id,requested_by_membership_id,assigned_membership_id,preflight_id,
            decision_id,job_id,functional_identity_fingerprint,idempotency_key_digest,request_fingerprint,correlation_id,state,
            created_at,updated_at
          ) VALUES (v_admission_id,v_org,v_prospect_id,v_version.id,p_membership_id,p_assigned_membership_id,v_preflight_id,
            v_decision_id,v_job_id,p_fingerprint,p_admission_digest,p_fingerprint,p_correlation_id,'ready_to_prepare',v_now,v_now);
          INSERT INTO public.audit_events (id,scope,organization_id,actor_kind,actor_id,action,entity_type,entity_id,request_id,
            correlation_id,source,metadata,schema_version,occurred_at)
          VALUES (gen_random_uuid(),'tenant',v_org,'user',v_actor,'prospect.created','prospect',v_prospect_id,p_request_id,
            p_correlation_id::text,'api',jsonb_build_object('origin','manual','automation',true),1,v_now);
          RETURN jsonb_build_object('code','accepted','prospect_id',v_prospect_id,'admission_id',v_admission_id,
            'job_id',v_job_id,'state','ready_to_prepare','replayed',false);
        END $fn$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.admit_manual_new_prospect_automation(text,uuid,uuid,text,text,text,uuid,boolean,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.admit_manual_new_prospect_automation(text,uuid,uuid,text,text,text,uuid,boolean,text) TO prospect_app"
    )

    op.execute("""
        CREATE FUNCTION app_private.prepare_automation_new_prospect_task(
          p_job_id uuid, p_prospect_id uuid, p_global_enabled boolean, p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          a public.automation_admissions%ROWTYPE; p public.prospects%ROWTYPE; v_task_id uuid; v_existing_fingerprint text;
          v_now timestamptz := clock_timestamp(); v_key text; v_fingerprint text;
        BEGIN
          SELECT a0.* INTO a FROM public.automation_admissions a0
          WHERE a0.job_id=p_job_id AND a0.prospect_id=p_prospect_id
            AND a0.organization_id=app_private.current_organization_id() FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION 'subject_missing'; END IF;
          IF a.state='prepared' AND a.task_id IS NOT NULL THEN
            RETURN jsonb_build_object('result_code','replayed','task_id',a.task_id);
          END IF;
          SELECT * INTO p FROM public.prospects WHERE id=a.prospect_id AND organization_id=a.organization_id FOR UPDATE;
          IF NOT FOUND OR p.archived_at IS NOT NULL THEN
            UPDATE public.automation_admissions SET state='blocked',result_code='prospect_not_writable',completed_at=v_now,updated_at=v_now WHERE id=a.id;
            RETURN jsonb_build_object('result_code','blocked');
          END IF;
          IF NOT p_global_enabled OR NOT EXISTS (SELECT 1 FROM public.organizations o WHERE o.id=a.organization_id AND o.status='active')
            OR NOT EXISTS (SELECT 1 FROM public.memberships m JOIN public.users u ON u.id=m.user_id WHERE m.id=a.requested_by_membership_id
              AND m.organization_id=a.organization_id AND m.status='active' AND u.status='active')
            OR NOT EXISTS (SELECT 1 FROM public.memberships m WHERE m.id=a.assigned_membership_id AND m.organization_id=a.organization_id AND m.status='active')
            OR NOT EXISTS (SELECT 1 FROM public.automation_organization_settings s WHERE s.organization_id=a.organization_id AND s.automation_enabled)
            OR NOT EXISTS (SELECT 1 FROM public.automation_playbooks b JOIN public.automation_playbook_versions v ON v.id=a.playbook_version_id
              WHERE b.id=v.playbook_id AND b.organization_id=a.organization_id AND b.state='active_prepare' AND b.prepare_enabled)
            OR NOT EXISTS (SELECT 1 FROM public.automation_preflights f WHERE f.id=a.preflight_id AND f.organization_id=a.organization_id
              AND f.state='completed' AND f.expires_at>v_now)
            OR NOT EXISTS (SELECT 1 FROM public.automation_decisions d WHERE d.id=a.decision_id AND d.organization_id=a.organization_id
              AND d.preflight_id=a.preflight_id AND d.subject_id=a.prospect_id AND d.next_action='prepare' AND d.outcome='prepared' AND d.expires_at>v_now)
          THEN
            UPDATE public.automation_admissions SET state='blocked',result_code='guard_blocked',completed_at=v_now,updated_at=v_now WHERE id=a.id;
            RETURN jsonb_build_object('result_code','blocked');
          END IF;
          v_key := 'automation-admission:' || a.idempotency_key_digest;
          v_fingerprint := encode(digest(jsonb_build_object('admission',a.request_fingerprint,'assigned_membership_id',a.assigned_membership_id,'title','Prendre en charge le prospect ' || p.internal_alias,'due_at',(a.created_at + interval '24 hours'))::text,'sha256'),'hex');
          SELECT id,command_fingerprint INTO v_task_id,v_existing_fingerprint FROM public.prospect_tasks
          WHERE organization_id=a.organization_id AND prospect_id=a.prospect_id AND idempotency_key=v_key FOR UPDATE;
          IF FOUND AND v_existing_fingerprint <> v_fingerprint THEN
            UPDATE public.automation_admissions SET state='to_verify',result_code='effect_uncertain',completed_at=v_now,updated_at=v_now WHERE id=a.id;
            RETURN jsonb_build_object('result_code','to_verify');
          END IF;
          IF NOT FOUND THEN
            INSERT INTO public.prospect_tasks (id,organization_id,prospect_id,created_by,assigned_membership_id,title,description,priority,status,due_at,created_at,updated_at,version,idempotency_key,command_fingerprint)
            VALUES (gen_random_uuid(),a.organization_id,a.prospect_id,(SELECT actor_id FROM public.jobs WHERE id=p_job_id),a.assigned_membership_id,
              'Prendre en charge le prospect ' || p.internal_alias,'Vérifier le contexte disponible et définir la prochaine action.','normal','open',a.created_at + interval '24 hours',v_now,v_now,1,v_key,v_fingerprint)
            RETURNING id INTO v_task_id;
            INSERT INTO public.prospect_task_events (id,organization_id,prospect_id,task_id,actor_id,event_type,resulting_status,resulting_version,changed_fields,occurred_at,idempotency_key,command_fingerprint)
            VALUES (gen_random_uuid(),a.organization_id,a.prospect_id,v_task_id,(SELECT actor_id FROM public.jobs WHERE id=p_job_id),'created','open',1,'{"title":"changed"}'::jsonb,v_now,v_key,v_fingerprint);
          END IF;
          UPDATE public.automation_admissions SET task_id=v_task_id,state='prepared',result_code='prepared',completed_at=v_now,updated_at=v_now WHERE id=a.id;
          INSERT INTO public.audit_events (id,scope,organization_id,actor_kind,actor_id,action,entity_type,entity_id,request_id,correlation_id,source,metadata,schema_version,occurred_at)
          VALUES (gen_random_uuid(),'tenant',a.organization_id,'user',(SELECT actor_id FROM public.jobs WHERE id=p_job_id),'prospect.task_created','prospect_task',v_task_id,p_request_id,a.correlation_id::text,'worker',jsonb_build_object('automation',true),1,v_now);
          RETURN jsonb_build_object('result_code','prepared','task_id',v_task_id);
        END $fn$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.prepare_automation_new_prospect_task(uuid,uuid,boolean,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.prepare_automation_new_prospect_task(uuid,uuid,boolean,text) TO prospect_worker"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.prepare_automation_new_prospect_task(uuid,uuid,boolean,text) FROM prospect_worker"
    )
    op.execute("DROP FUNCTION app_private.prepare_automation_new_prospect_task(uuid,uuid,boolean,text)")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.admit_manual_new_prospect_automation(text,uuid,uuid,text,text,text,uuid,boolean,text) FROM prospect_app"
    )
    op.execute(
        "DROP FUNCTION app_private.admit_manual_new_prospect_automation(text,uuid,uuid,text,text,text,uuid,boolean,text)"
    )
    op.execute("DROP POLICY IF EXISTS automation_admissions_worker_runtime ON public.automation_admissions")
    op.execute("REVOKE SELECT, UPDATE ON public.automation_admissions FROM prospect_worker")
    op.drop_index("uq_automation_admissions_org_job", table_name="automation_admissions")
    op.drop_constraint("fk_automation_admissions_org_assignee", "automation_admissions", type_="foreignkey")
    op.drop_column("automation_admissions", "assigned_membership_id")
