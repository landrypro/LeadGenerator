"""Harden the P52 effective entitlement engine with provenance and safety ceilings.

Revision ID: 20261008_0048
Revises: 20261007_0047
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261008_0048"
down_revision: str | Sequence[str] | None = "20261007_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This is a technical safety policy, deliberately separate from a price or
    # a contract.  Empty is valid: a ceiling is applied only after an explicit
    # platform safety decision has created one.
    op.execute(
        """
        CREATE TABLE public.entitlement_safety_ceilings (
          entitlement_key varchar(64) PRIMARY KEY,
          value_kind varchar(16) NOT NULL,
          integer_value bigint NULL,
          boolean_value boolean NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT ck_entitlement_safety_ceilings_key_allowed CHECK (entitlement_key IN (
            'seats.active_members.max','seats.pending_invitations.max','prospects.active.max',
            'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',
            'automation.prepare.enabled','automation.execute.enabled')),
          CONSTRAINT ck_entitlement_safety_ceilings_kind_allowed CHECK (value_kind IN ('limit','switch')),
          CONSTRAINT ck_entitlement_safety_ceilings_typed_value CHECK (
            (value_kind='limit' AND integer_value IS NOT NULL AND integer_value >= 0 AND boolean_value IS NULL)
            OR (value_kind='switch' AND boolean_value IS NOT NULL AND integer_value IS NULL))
        )
        """
    )
    op.execute("REVOKE ALL ON public.entitlement_safety_ceilings FROM PUBLIC, prospect_app")
    op.execute("GRANT SELECT ON public.entitlement_safety_ceilings TO prospect_rls_definer")

    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.tenant_effective_entitlement(
          p_entitlement_key text, p_now timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_organization_id uuid := app_private.current_organization_id();
          v_contract_count integer;
          v_override_count integer;
          v_contract public.organization_plan_contracts%ROWTYPE;
          v_version public.plan_versions%ROWTYPE;
          v_entitlement public.plan_entitlements%ROWTYPE;
          v_override public.plan_contract_overrides%ROWTYPE;
          v_safety public.entitlement_safety_ceilings%ROWTYPE;
          v_value_kind text;
          v_integer_value bigint;
          v_boolean_value boolean;
          v_source text;
          v_provenance jsonb;
        BEGIN
          IF p_entitlement_key NOT IN (
            'seats.active_members.max','seats.pending_invitations.max','prospects.active.max',
            'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',
            'automation.prepare.enabled','automation.execute.enabled') THEN
            RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key,
              'reason','entitlement_unknown','provenance','[]'::jsonb);
          END IF;

          SELECT count(*) INTO v_contract_count FROM public.organization_plan_contracts
          WHERE organization_id=v_organization_id AND state='active'
            AND effective_from <= p_now AND (effective_until IS NULL OR effective_until > p_now);
          IF v_contract_count <> 1 THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason',CASE WHEN v_contract_count=0 THEN 'contract_not_active' ELSE 'ambiguous_active_contract' END,
              'provenance',jsonb_build_array(jsonb_build_object('source','contract','applied',false)));
          END IF;
          SELECT * INTO v_contract FROM public.organization_plan_contracts
          WHERE organization_id=v_organization_id AND state='active'
            AND effective_from <= p_now AND (effective_until IS NULL OR effective_until > p_now);
          v_provenance := jsonb_build_array(jsonb_build_object('source','contract','applied',true));

          SELECT * INTO v_version FROM public.plan_versions WHERE id=v_contract.plan_version_id;
          IF NOT FOUND OR v_version.state <> 'published' THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason','catalog_version_not_published','provenance',v_provenance);
          END IF;
          IF v_version.effective_from > p_now OR (v_version.effective_until IS NOT NULL AND v_version.effective_until <= p_now) THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason','catalog_version_not_effective','provenance',v_provenance);
          END IF;
          IF v_version.currency <> v_contract.currency THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason','contract_currency_mismatch','provenance',v_provenance);
          END IF;
          v_provenance := v_provenance || jsonb_build_array(jsonb_build_object('source','plan_version','applied',true));

          SELECT * INTO v_entitlement FROM public.plan_entitlements
          WHERE plan_version_id=v_version.id AND entitlement_key=p_entitlement_key;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key,
              'reason','plan_entitlement_missing','provenance',v_provenance);
          END IF;

          SELECT count(*) INTO v_override_count FROM public.plan_contract_overrides
          WHERE organization_id=v_organization_id AND contract_id=v_contract.id AND entitlement_key=p_entitlement_key
            AND state='active' AND starts_at <= p_now AND ends_at > p_now;
          IF v_override_count > 1 THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason','ambiguous_active_override','provenance',v_provenance);
          END IF;
          IF v_override_count = 1 THEN
            SELECT * INTO v_override FROM public.plan_contract_overrides
            WHERE organization_id=v_organization_id AND contract_id=v_contract.id AND entitlement_key=p_entitlement_key
              AND state='active' AND starts_at <= p_now AND ends_at > p_now;
            IF v_override.approved_by_user_id IS NULL OR v_override.approved_by_user_id=v_override.requested_by_user_id THEN
              RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key,
                'reason','override_not_approved','provenance',v_provenance || jsonb_build_array(jsonb_build_object('source','override','applied',false)));
            END IF;
            IF v_override.value_kind <> v_entitlement.value_kind THEN
              RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key,
                'reason','override_kind_mismatch','provenance',v_provenance || jsonb_build_array(jsonb_build_object('source','override','applied',false)));
            END IF;
            v_value_kind := v_override.value_kind;
            v_integer_value := v_override.integer_value;
            v_boolean_value := v_override.boolean_value;
            v_source := 'override';
            v_provenance := v_provenance || jsonb_build_array(jsonb_build_object('source','override','applied',true));
          ELSE
            v_value_kind := v_entitlement.value_kind;
            v_integer_value := v_entitlement.integer_value;
            v_boolean_value := v_entitlement.boolean_value;
            v_source := 'plan_version';
          END IF;

          SELECT * INTO v_safety FROM public.entitlement_safety_ceilings WHERE entitlement_key=p_entitlement_key;
          IF FOUND THEN
            IF v_safety.value_kind <> v_value_kind
              OR (v_value_kind='limit' AND v_integer_value > v_safety.integer_value)
              OR (v_value_kind='switch' AND v_boolean_value AND NOT v_safety.boolean_value) THEN
              RETURN jsonb_build_object('code','safety_ceiling_exceeded','key',p_entitlement_key,
                'source',v_source,'reason','safety_ceiling_exceeded',
                'provenance',v_provenance || jsonb_build_array(jsonb_build_object('source','safety_ceiling','applied',false)));
            END IF;
            v_provenance := v_provenance || jsonb_build_array(jsonb_build_object('source','safety_ceiling','applied',true));
          END IF;

          RETURN jsonb_build_object(
            'code',CASE WHEN (v_value_kind='limit' AND v_integer_value=0) OR (v_value_kind='switch' AND NOT v_boolean_value)
              THEN 'entitlement_disabled' ELSE 'allowed' END,
            'key',p_entitlement_key,'source',v_source,'value_kind',v_value_kind,
            'integer_value',v_integer_value,'boolean_value',v_boolean_value,
            'provenance',v_provenance
          );
        END $fn$;
        """
    )


def downgrade() -> None:
    # Replace the body before removing the composite type used by %ROWTYPE.
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.tenant_effective_entitlement(
          p_entitlement_key text, p_now timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_organization_id uuid := app_private.current_organization_id();
          v_contract public.organization_plan_contracts%ROWTYPE;
          v_version public.plan_versions%ROWTYPE;
          v_entitlement public.plan_entitlements%ROWTYPE;
          v_override public.plan_contract_overrides%ROWTYPE;
        BEGIN
          IF p_entitlement_key NOT IN (
            'seats.active_members.max','seats.pending_invitations.max','prospects.active.max',
            'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',
            'automation.prepare.enabled','automation.execute.enabled') THEN
            RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key);
          END IF;
          SELECT * INTO v_contract FROM public.organization_plan_contracts
          WHERE organization_id=v_organization_id AND state='active'
            AND effective_from <= p_now AND (effective_until IS NULL OR effective_until > p_now)
          ORDER BY effective_from DESC, created_at DESC LIMIT 1;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key);
          END IF;
          SELECT * INTO v_version FROM public.plan_versions WHERE id=v_contract.plan_version_id;
          IF NOT FOUND OR v_version.state <> 'published' OR v_version.currency <> v_contract.currency THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key);
          END IF;
          SELECT * INTO v_entitlement FROM public.plan_entitlements
          WHERE plan_version_id=v_version.id AND entitlement_key=p_entitlement_key;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key);
          END IF;
          SELECT * INTO v_override FROM public.plan_contract_overrides
          WHERE organization_id=v_organization_id AND contract_id=v_contract.id AND entitlement_key=p_entitlement_key
            AND state='active' AND starts_at <= p_now AND ends_at > p_now
          ORDER BY starts_at DESC LIMIT 1;
          IF FOUND THEN
            RETURN jsonb_build_object('code',CASE WHEN (v_override.value_kind='limit' AND v_override.integer_value=0)
                OR (v_override.value_kind='switch' AND NOT v_override.boolean_value) THEN 'entitlement_disabled' ELSE 'allowed' END,
              'key',p_entitlement_key,'source','override',
              'value_kind',v_override.value_kind,'integer_value',v_override.integer_value,
              'boolean_value',v_override.boolean_value,'contract_id',v_contract.id);
          END IF;
          RETURN jsonb_build_object('code',CASE WHEN (v_entitlement.value_kind='limit' AND v_entitlement.integer_value=0)
              OR (v_entitlement.value_kind='switch' AND NOT v_entitlement.boolean_value) THEN 'entitlement_disabled' ELSE 'allowed' END,
            'key',p_entitlement_key,'source','plan_version',
            'value_kind',v_entitlement.value_kind,'integer_value',v_entitlement.integer_value,
            'boolean_value',v_entitlement.boolean_value,'contract_id',v_contract.id);
        END $fn$;
        """
    )
    op.execute("DROP TABLE public.entitlement_safety_ceilings")
