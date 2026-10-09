"""Atomic internal catalog and contract mutations for P52-03."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261007_0043"
down_revision: str | None = "20261006_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAN = "app_private.platform_create_catalog_plan(uuid,text,integer,timestamp with time zone)"
_VERSION = "app_private.platform_create_catalog_version(uuid,uuid,integer,text,text,bigint,timestamp with time zone,timestamp with time zone,jsonb,timestamp with time zone)"
_PUBLISH = "app_private.platform_publish_catalog_version(uuid,integer,timestamp with time zone)"
_ATTACH = "app_private.platform_attach_catalog_contract(uuid,uuid,uuid,text,timestamp with time zone,timestamp with time zone,timestamp with time zone)"
_STATE = "app_private.platform_change_catalog_contract_state(uuid,integer,text,timestamp with time zone)"


def upgrade() -> None:
    op.execute("ALTER TABLE public.plan_versions ADD COLUMN version integer NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE public.plan_versions ADD CONSTRAINT ck_plan_versions_version_positive CHECK (version > 0)")
    op.execute(
        "GRANT INSERT, UPDATE ON public.plan_catalog, public.plan_versions, public.plan_entitlements TO prospect_rls_definer"
    )
    op.execute("GRANT INSERT, UPDATE ON public.organization_plan_contracts TO prospect_rls_definer")
    for table in ("organization_plan_contracts", "plan_contract_overrides"):
        op.execute(
            f"CREATE POLICY {table}_platform_mutation ON public.{table} FOR ALL TO prospect_rls_definer USING (true) WITH CHECK (true)"
        )
    op.execute(r"""
      CREATE FUNCTION app_private.platform_create_catalog_plan(p_id uuid,p_code text,p_order integer,p_now timestamptz)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $f$
      DECLARE v_actor uuid:=app_private.current_actor_id(); v_plan public.plan_catalog%ROWTYPE;
      BEGIN
        IF v_actor IS NULL OR p_code NOT IN ('freemium','starter','business','custom') OR p_order<0 THEN RETURN jsonb_build_object('code','invalid_contract'); END IF;
        IF NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active') THEN RETURN jsonb_build_object('code','invalid_contract'); END IF;
        INSERT INTO public.plan_catalog(id,code,state,display_order,created_at,updated_at,version)
        VALUES(p_id,p_code,'draft',p_order,p_now,p_now,1) ON CONFLICT(code) DO NOTHING RETURNING * INTO v_plan;
        IF NOT FOUND THEN RETURN jsonb_build_object('code','conflict'); END IF;
        RETURN jsonb_build_object('code','created','plan',jsonb_build_object('id',v_plan.id,'code',v_plan.code,'state',v_plan.state,'display_order',v_plan.display_order,'version',v_plan.version));
      END $f$;
    """)
    op.execute(r"""
      CREATE FUNCTION app_private.platform_create_catalog_version(
        p_id uuid,p_plan_id uuid,p_number integer,p_currency text,p_cycle text,p_amount bigint,p_from timestamptz,p_until timestamptz,p_rights jsonb,p_now timestamptz)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $f$
      DECLARE v_actor uuid:=app_private.current_actor_id(); v_plan public.plan_catalog%ROWTYPE; v_version public.plan_versions%ROWTYPE; v_item record; v_count integer; v_unit text; v_scope text;
      BEGIN
        IF v_actor IS NULL OR p_number<1 OR p_currency NOT IN('CAD','USD','EUR','XAF') OR p_cycle NOT IN('monthly','annual','custom_contract') OR p_amount<0 OR (p_until IS NOT NULL AND p_until<=p_from) OR jsonb_typeof(p_rights)<>'array' THEN RETURN jsonb_build_object('code','invalid_contract'); END IF;
        SELECT * INTO v_plan FROM public.plan_catalog WHERE id=p_plan_id AND state<>'retired' FOR UPDATE;
        IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
        IF jsonb_array_length(p_rights)<>8 OR (SELECT count(DISTINCT key) FROM jsonb_to_recordset(p_rights) AS e(key text,kind text,integer_value bigint,boolean_value boolean))<>8 THEN RETURN jsonb_build_object('code','invalid_contract'); END IF;
        FOR v_item IN SELECT * FROM jsonb_to_recordset(p_rights) AS e(key text,kind text,integer_value bigint,boolean_value boolean) LOOP
          v_unit:=CASE v_item.key WHEN 'seats.active_members.max' THEN 'seat' WHEN 'seats.pending_invitations.max' THEN 'reserved_seat' WHEN 'prospects.active.max' THEN 'prospect' WHEN 'exports.monthly.max' THEN 'export' WHEN 'imports.rows_per_run.max' THEN 'row' WHEN 'google.paid_calls.enabled' THEN 'boolean' WHEN 'automation.prepare.enabled' THEN 'boolean' WHEN 'automation.execute.enabled' THEN 'boolean' END;
          v_scope:=CASE v_item.key WHEN 'exports.monthly.max' THEN 'period' WHEN 'imports.rows_per_run.max' THEN 'run' WHEN 'seats.active_members.max' THEN 'organization' WHEN 'seats.pending_invitations.max' THEN 'organization' WHEN 'prospects.active.max' THEN 'organization' WHEN 'google.paid_calls.enabled' THEN 'organization' WHEN 'automation.prepare.enabled' THEN 'organization' WHEN 'automation.execute.enabled' THEN 'organization' END;
          IF v_unit IS NULL OR v_item.kind NOT IN('limit','switch') OR (v_item.kind='limit' AND (v_item.integer_value IS NULL OR v_item.integer_value<0 OR v_item.boolean_value IS NOT NULL)) OR (v_item.kind='switch' AND (v_item.boolean_value IS NULL OR v_item.integer_value IS NOT NULL)) THEN RETURN jsonb_build_object('code','invalid_contract'); END IF;
        END LOOP;
        INSERT INTO public.plan_versions(id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,effective_from,effective_until,created_by_user_id,created_at,version)
        VALUES(p_id,p_plan_id,p_number,'draft',p_currency,p_cycle,p_amount,p_from,p_until,v_actor,p_now,1) ON CONFLICT(plan_id,version_number) DO NOTHING RETURNING * INTO v_version;
        IF NOT FOUND THEN RETURN jsonb_build_object('code','conflict'); END IF;
        FOR v_item IN SELECT * FROM jsonb_to_recordset(p_rights) AS e(key text,kind text,integer_value bigint,boolean_value boolean) LOOP
          v_unit:=CASE v_item.key WHEN 'seats.active_members.max' THEN 'seat' WHEN 'seats.pending_invitations.max' THEN 'reserved_seat' WHEN 'prospects.active.max' THEN 'prospect' WHEN 'exports.monthly.max' THEN 'export' WHEN 'imports.rows_per_run.max' THEN 'row' ELSE 'boolean' END;
          v_scope:=CASE v_item.key WHEN 'exports.monthly.max' THEN 'period' WHEN 'imports.rows_per_run.max' THEN 'run' ELSE 'organization' END;
          INSERT INTO public.plan_entitlements(id,plan_version_id,entitlement_key,value_kind,integer_value,boolean_value,unit,scope,created_at) VALUES(gen_random_uuid(),p_id,v_item.key,v_item.kind,v_item.integer_value,v_item.boolean_value,v_unit,v_scope,p_now);
        END LOOP;
        RETURN jsonb_build_object('code','created','plan_version',jsonb_build_object('id',v_version.id,'plan_id',v_version.plan_id,'version_number',v_version.version_number,'state',v_version.state,'currency',v_version.currency,'billing_cycle',v_version.billing_cycle,'amount_excluding_tax_minor',v_version.amount_excluding_tax_minor,'effective_from',v_version.effective_from,'effective_until',v_version.effective_until,'version',v_version.version));
      END $f$;
    """)
    op.execute(r"""
      CREATE FUNCTION app_private.platform_publish_catalog_version(p_id uuid,p_expected integer,p_now timestamptz)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $f$
      DECLARE v_actor uuid:=app_private.current_actor_id(); v_version public.plan_versions%ROWTYPE;
      BEGIN
        SELECT * INTO v_version FROM public.plan_versions WHERE id=p_id FOR UPDATE; IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
        IF p_expected<>v_version.version THEN RETURN jsonb_build_object('code','version_conflict','current_version',v_version.version); END IF;
        IF v_version.state<>'draft' THEN RETURN jsonb_build_object('code','invalid_transition'); END IF;
        IF v_actor IS NULL OR v_actor=v_version.created_by_user_id THEN RETURN jsonb_build_object('code','approval_required'); END IF;
        UPDATE public.plan_versions SET state='published',approved_by_user_id=v_actor,published_at=p_now,version=version+1 WHERE id=p_id RETURNING * INTO v_version;
        UPDATE public.plan_catalog SET state='published',updated_at=p_now,version=version+1 WHERE id=v_version.plan_id AND state='draft';
        RETURN jsonb_build_object('code','published','plan_version',jsonb_build_object('id',v_version.id,'plan_id',v_version.plan_id,'version_number',v_version.version_number,'state',v_version.state,'currency',v_version.currency,'billing_cycle',v_version.billing_cycle,'amount_excluding_tax_minor',v_version.amount_excluding_tax_minor,'effective_from',v_version.effective_from,'effective_until',v_version.effective_until,'version',v_version.version));
      END $f$;
    """)
    op.execute(r"""
      CREATE FUNCTION app_private.platform_attach_catalog_contract(p_id uuid,p_org uuid,p_plan_version uuid,p_state text,p_from timestamptz,p_until timestamptz,p_now timestamptz)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $f$
      DECLARE v_actor uuid:=app_private.current_actor_id(); v_plan public.plan_versions%ROWTYPE; v_contract public.organization_plan_contracts%ROWTYPE;
      BEGIN
        IF v_actor IS NULL OR p_state NOT IN('pending','active') OR(p_until IS NOT NULL AND p_until<=p_from) THEN RETURN jsonb_build_object('code','invalid_contract'); END IF;
        IF NOT EXISTS(SELECT 1 FROM public.organizations WHERE id=p_org) THEN RETURN jsonb_build_object('code','not_found'); END IF;
        SELECT * INTO v_plan FROM public.plan_versions WHERE id=p_plan_version AND state='published'; IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
        IF EXISTS(SELECT 1 FROM public.organization_plan_contracts WHERE organization_id=p_org AND state IN('pending','active','suspended')) THEN RETURN jsonb_build_object('code','conflict'); END IF;
        INSERT INTO public.organization_plan_contracts(id,organization_id,plan_version_id,state,currency,effective_from,effective_until,created_by_user_id,updated_by_user_id,created_at,updated_at,version)
        VALUES(p_id,p_org,p_plan_version,p_state,v_plan.currency,p_from,p_until,v_actor,v_actor,p_now,p_now,1) RETURNING * INTO v_contract;
        RETURN jsonb_build_object('code','created','contract',jsonb_build_object('id',v_contract.id,'organization_id',v_contract.organization_id,'plan_version_id',v_contract.plan_version_id,'state',v_contract.state,'currency',v_contract.currency,'effective_from',v_contract.effective_from,'effective_until',v_contract.effective_until,'version',v_contract.version));
      END $f$;
    """)
    op.execute(r"""
      CREATE FUNCTION app_private.platform_change_catalog_contract_state(p_id uuid,p_expected integer,p_state text,p_now timestamptz)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $f$
      DECLARE v_actor uuid:=app_private.current_actor_id(); v_contract public.organization_plan_contracts%ROWTYPE;
      BEGIN
        SELECT * INTO v_contract FROM public.organization_plan_contracts WHERE id=p_id FOR UPDATE; IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
        IF p_expected<>v_contract.version THEN RETURN jsonb_build_object('code','version_conflict','current_version',v_contract.version); END IF;
        IF v_actor IS NULL OR NOT((v_contract.state='pending' AND p_state IN('active','ended')) OR(v_contract.state='active' AND p_state IN('suspended','ended')) OR(v_contract.state='suspended' AND p_state IN('active','ended'))) THEN RETURN jsonb_build_object('code','invalid_transition'); END IF;
        UPDATE public.organization_plan_contracts SET state=p_state,updated_by_user_id=v_actor,updated_at=p_now,version=version+1 WHERE id=p_id RETURNING * INTO v_contract;
        RETURN jsonb_build_object('code','updated','contract',jsonb_build_object('id',v_contract.id,'organization_id',v_contract.organization_id,'plan_version_id',v_contract.plan_version_id,'state',v_contract.state,'currency',v_contract.currency,'effective_from',v_contract.effective_from,'effective_until',v_contract.effective_until,'version',v_contract.version));
      END $f$;
    """)
    for signature in (_PLAN, _VERSION, _PUBLISH, _ATTACH, _STATE):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    for signature in (_STATE, _ATTACH, _PUBLISH, _VERSION, _PLAN):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM prospect_app")
        op.execute(f"DROP FUNCTION {signature}")
    for table in ("plan_contract_overrides", "organization_plan_contracts"):
        op.execute(f"DROP POLICY {table}_platform_mutation ON public.{table}")
    op.execute("REVOKE INSERT, UPDATE ON public.organization_plan_contracts FROM prospect_rls_definer")
    op.execute(
        "REVOKE INSERT, UPDATE ON public.plan_catalog, public.plan_versions, public.plan_entitlements FROM prospect_rls_definer"
    )
    op.execute("ALTER TABLE public.plan_versions DROP CONSTRAINT ck_plan_versions_version_positive")
    op.execute("ALTER TABLE public.plan_versions DROP COLUMN version")
