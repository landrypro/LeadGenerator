"""Add the P5.2 versioned catalog and fail-closed entitlement foundation.

Revision ID: 20261005_0039
Revises: 20261005_0038
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261005_0039"
down_revision: str | None = "20261005_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITLEMENT_SIGNATURE = "(text,timestamp with time zone)"


def upgrade() -> None:
    # The extension only supplies the GiST equality operator needed to prevent
    # ambiguous override periods.  It has no payment or external-service role.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        CREATE TABLE public.plan_catalog (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          code varchar(32) NOT NULL,
          state varchar(16) NOT NULL DEFAULT 'draft',
          display_order integer NOT NULL DEFAULT 0,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT uq_plan_catalog_code UNIQUE (code),
          CONSTRAINT ck_plan_catalog_code_allowed CHECK (code IN ('freemium','starter','business','custom')),
          CONSTRAINT ck_plan_catalog_state_allowed CHECK (state IN ('draft','published','retired')),
          CONSTRAINT ck_plan_catalog_display_order_nonnegative CHECK (display_order >= 0),
          CONSTRAINT ck_plan_catalog_version_positive CHECK (version > 0)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.plan_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          plan_id uuid NOT NULL REFERENCES public.plan_catalog(id) ON DELETE RESTRICT,
          version_number integer NOT NULL,
          state varchar(16) NOT NULL DEFAULT 'draft',
          currency varchar(3) NOT NULL,
          billing_cycle varchar(32) NOT NULL,
          amount_excluding_tax_minor bigint NOT NULL,
          effective_from timestamptz NOT NULL,
          effective_until timestamptz NULL,
          created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          approved_by_user_id uuid NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          published_at timestamptz NULL,
          CONSTRAINT uq_plan_versions_plan_number UNIQUE (plan_id, version_number),
          CONSTRAINT ck_plan_versions_state_allowed CHECK (state IN ('draft','published','superseded','retired')),
          CONSTRAINT ck_plan_versions_currency_allowed CHECK (currency IN ('CAD','USD','EUR','XAF')),
          CONSTRAINT ck_plan_versions_cycle_allowed CHECK (billing_cycle IN ('monthly','annual','custom_contract')),
          CONSTRAINT ck_plan_versions_amount_nonnegative CHECK (amount_excluding_tax_minor >= 0),
          CONSTRAINT ck_plan_versions_number_positive CHECK (version_number > 0),
          CONSTRAINT ck_plan_versions_effective_range CHECK (effective_until IS NULL OR effective_until > effective_from),
          CONSTRAINT ck_plan_versions_published_approval CHECK (
            state <> 'published' OR (approved_by_user_id IS NOT NULL
              AND approved_by_user_id <> created_by_user_id AND published_at IS NOT NULL))
        )
        """
    )
    op.execute("CREATE INDEX ix_plan_versions_plan_state ON public.plan_versions(plan_id, state)")
    op.execute(
        """
        CREATE TABLE public.plan_entitlements (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          plan_version_id uuid NOT NULL REFERENCES public.plan_versions(id) ON DELETE CASCADE,
          entitlement_key varchar(64) NOT NULL,
          value_kind varchar(16) NOT NULL,
          integer_value bigint NULL,
          boolean_value boolean NULL,
          unit varchar(32) NOT NULL,
          scope varchar(32) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT uq_plan_entitlements_version_key UNIQUE (plan_version_id, entitlement_key),
          CONSTRAINT ck_plan_entitlements_key_allowed CHECK (entitlement_key IN (
            'seats.active_members.max','seats.pending_invitations.max','prospects.active.max',
            'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',
            'automation.prepare.enabled','automation.execute.enabled')),
          CONSTRAINT ck_plan_entitlements_kind_allowed CHECK (value_kind IN ('limit','switch')),
          CONSTRAINT ck_plan_entitlements_typed_value CHECK (
            (value_kind='limit' AND integer_value IS NOT NULL AND integer_value >= 0 AND boolean_value IS NULL)
            OR (value_kind='switch' AND boolean_value IS NOT NULL AND integer_value IS NULL)),
          CONSTRAINT ck_plan_entitlements_key_unit_scope CHECK (
            (entitlement_key='seats.active_members.max' AND unit='seat' AND scope='organization') OR
            (entitlement_key='seats.pending_invitations.max' AND unit='reserved_seat' AND scope='organization') OR
            (entitlement_key='prospects.active.max' AND unit='prospect' AND scope='organization') OR
            (entitlement_key='exports.monthly.max' AND unit='export' AND scope='period') OR
            (entitlement_key='imports.rows_per_run.max' AND unit='row' AND scope='run') OR
            (entitlement_key IN ('google.paid_calls.enabled','automation.prepare.enabled','automation.execute.enabled')
             AND unit='boolean' AND scope='organization'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.organization_plan_contracts (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          plan_version_id uuid NOT NULL REFERENCES public.plan_versions(id) ON DELETE RESTRICT,
          state varchar(16) NOT NULL DEFAULT 'pending',
          currency varchar(3) NOT NULL,
          effective_from timestamptz NOT NULL,
          effective_until timestamptz NULL,
          created_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          updated_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT uq_organization_plan_contracts_org_id UNIQUE (organization_id, id),
          CONSTRAINT ck_organization_plan_contracts_state_allowed CHECK (state IN ('pending','active','suspended','ended')),
          CONSTRAINT ck_organization_plan_contracts_currency_allowed CHECK (currency IN ('CAD','USD','EUR','XAF')),
          CONSTRAINT ck_organization_plan_contracts_effective_range CHECK (effective_until IS NULL OR effective_until > effective_from),
          CONSTRAINT ck_organization_plan_contracts_version_positive CHECK (version > 0)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_organization_plan_contracts_current "
        "ON public.organization_plan_contracts(organization_id) "
        "WHERE state IN ('pending','active','suspended')"
    )
    op.execute(
        "CREATE INDEX ix_organization_plan_contracts_org_state "
        "ON public.organization_plan_contracts(organization_id, state, effective_from)"
    )
    op.execute(
        """
        CREATE TABLE public.plan_contract_overrides (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          contract_id uuid NOT NULL,
          entitlement_key varchar(64) NOT NULL,
          value_kind varchar(16) NOT NULL,
          integer_value bigint NULL,
          boolean_value boolean NULL,
          state varchar(32) NOT NULL DEFAULT 'pending_approval',
          justification varchar(512) NOT NULL,
          requested_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          approved_by_user_id uuid NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          starts_at timestamptz NOT NULL,
          ends_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT uq_plan_contract_overrides_org_id UNIQUE (organization_id, id),
          CONSTRAINT fk_plan_contract_overrides_organization_id_contract_id_organization_plan_contracts
            FOREIGN KEY (organization_id, contract_id)
            REFERENCES public.organization_plan_contracts(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_plan_contract_overrides_state_allowed CHECK (state IN ('pending_approval','active','expired','revoked')),
          CONSTRAINT ck_plan_contract_overrides_key_allowed CHECK (entitlement_key IN (
            'seats.active_members.max','seats.pending_invitations.max','prospects.active.max',
            'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',
            'automation.prepare.enabled','automation.execute.enabled')),
          CONSTRAINT ck_plan_contract_overrides_kind_allowed CHECK (value_kind IN ('limit','switch')),
          CONSTRAINT ck_plan_contract_overrides_typed_value CHECK (
            (value_kind='limit' AND integer_value IS NOT NULL AND integer_value >= 0 AND boolean_value IS NULL)
            OR (value_kind='switch' AND boolean_value IS NOT NULL AND integer_value IS NULL)),
          CONSTRAINT ck_plan_contract_overrides_justification_length CHECK (char_length(justification) BETWEEN 1 AND 512),
          CONSTRAINT ck_plan_contract_overrides_active_range CHECK (ends_at > starts_at),
          CONSTRAINT ck_plan_contract_overrides_version_positive CHECK (version > 0),
          CONSTRAINT ex_plan_contract_overrides_no_overlap EXCLUDE USING gist (
            organization_id WITH =, entitlement_key WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&
          ) WHERE (state IN ('pending_approval','active'))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_plan_contract_overrides_org_contract "
        "ON public.plan_contract_overrides(organization_id, contract_id, state)"
    )

    # A published version is a historical commercial record.  The trigger
    # makes direct SQL changes fail as well, not only application mutations.
    op.execute(
        r"""
        CREATE FUNCTION app_private.guard_plan_catalog_immutability()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_state text;
        BEGIN
          IF TG_TABLE_NAME='plan_catalog' THEN
            IF TG_OP='UPDATE' AND OLD.code IS DISTINCT FROM NEW.code THEN
              RAISE EXCEPTION 'plan_code_immutable';
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
          END IF;
          IF TG_TABLE_NAME='plan_versions' THEN
            IF OLD.state='published' AND TG_OP='DELETE' THEN
              RAISE EXCEPTION 'published_plan_version_immutable';
            END IF;
            IF OLD.state='published' AND TG_OP='UPDATE' AND (
              NEW.state NOT IN ('superseded','retired')
              OR (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state')
            ) THEN RAISE EXCEPTION 'published_plan_version_immutable'; END IF;
            IF TG_OP='UPDATE' AND NEW.state='published' AND OLD.state='draft' AND NOT EXISTS (
              SELECT 1 FROM public.plan_entitlements WHERE plan_version_id=NEW.id
              GROUP BY plan_version_id HAVING count(*)=8
            ) THEN RAISE EXCEPTION 'published_plan_version_incomplete'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
          END IF;
          SELECT state INTO v_state FROM public.plan_versions
          WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.plan_version_id ELSE NEW.plan_version_id END;
          IF v_state='published' THEN
            RAISE EXCEPTION 'published_plan_entitlements_immutable';
          END IF;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $fn$;
        """
    )
    op.execute("ALTER FUNCTION app_private.guard_plan_catalog_immutability() OWNER TO prospect_rls_definer")
    op.execute("REVOKE ALL ON FUNCTION app_private.guard_plan_catalog_immutability() FROM PUBLIC")
    for table in ("plan_catalog", "plan_versions", "plan_entitlements"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutability BEFORE INSERT OR UPDATE OR DELETE ON public.{table} "
            "FOR EACH ROW EXECUTE FUNCTION app_private.guard_plan_catalog_immutability()"
        )

    for table in ("organization_plan_contracts", "plan_contract_overrides"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_read ON public.{table} FOR SELECT TO prospect_app "
            "USING (organization_id=app_private.current_organization_id())"
        )
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON public.{table} TO prospect_app")
    for table in ("plan_catalog", "plan_versions", "plan_entitlements"):
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC, prospect_app")
    # Les fonctions SECURITY DEFINER lisent les sources canoniques sous ce
    # rôle technique sans connexion. Le rôle Web ne reçoit aucun droit direct
    # supplémentaire sur le catalogue global.
    op.execute(
        "GRANT SELECT ON public.plan_catalog, public.plan_versions, public.plan_entitlements, "
        "public.organization_plan_contracts, public.plan_contract_overrides TO prospect_rls_definer"
    )

    op.execute(
        r"""
        CREATE FUNCTION app_private.tenant_effective_entitlement(
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
    op.execute(
        "ALTER FUNCTION app_private.tenant_effective_entitlement(text, timestamp with time zone) OWNER TO prospect_rls_definer"
    )
    op.execute(f"REVOKE ALL ON FUNCTION app_private.tenant_effective_entitlement{_ENTITLEMENT_SIGNATURE} FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION app_private.tenant_effective_entitlement{_ENTITLEMENT_SIGNATURE} TO prospect_app"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION app_private.tenant_effective_entitlement{_ENTITLEMENT_SIGNATURE} FROM prospect_app"
    )
    op.execute(f"DROP FUNCTION app_private.tenant_effective_entitlement{_ENTITLEMENT_SIGNATURE}")
    op.execute(
        "REVOKE SELECT ON public.plan_catalog, public.plan_versions, public.plan_entitlements, "
        "public.organization_plan_contracts, public.plan_contract_overrides FROM prospect_rls_definer"
    )
    for table in ("organization_plan_contracts", "plan_contract_overrides"):
        op.execute(f"DROP POLICY {table}_tenant_read ON public.{table}")
    for table in ("plan_entitlements", "plan_versions", "plan_catalog"):
        op.execute(f"DROP TRIGGER trg_{table}_immutability ON public.{table}")
    op.execute("DROP FUNCTION app_private.guard_plan_catalog_immutability()")
    op.execute("DROP TABLE public.plan_contract_overrides")
    op.execute("DROP TABLE public.organization_plan_contracts")
    op.execute("DROP TABLE public.plan_entitlements")
    op.execute("DROP TABLE public.plan_versions")
    op.execute("DROP TABLE public.plan_catalog")
