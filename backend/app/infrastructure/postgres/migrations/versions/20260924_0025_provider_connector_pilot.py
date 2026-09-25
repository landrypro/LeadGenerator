"""Phase 4.5 controlled provider contracts and Meta Lead Ads pilot.

Revision ID: 20260924_0025
Revises: 20260924_0024
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260924_0025"
down_revision = "20260924_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgcrypto stores the upstream lead reference encrypted. No raw webhook body is persisted.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "provider_connector_contracts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("connector_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("evidence_ref", sa.String(256), nullable=True),
        sa.Column("meta_app_reference", sa.String(128), nullable=True),
        sa.Column("requested_permissions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("approved_permissions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("creator_membership_id", sa.Uuid(), nullable=False),
        sa.Column("review_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewer_membership_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "creator_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewer_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_connector_contracts_org_id"),
        sa.UniqueConstraint("organization_id", "provider_id", "connector_code", name="uq_connector_contracts_provider"),
        sa.CheckConstraint("connector_code = 'meta_lead_ads'", name="ck_connector_contract_code"),
        sa.CheckConstraint(
            "status IN ('draft','pending_review','approved','suspended','revoked','expired')",
            name="ck_connector_contract_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(requested_permissions) = 'array' AND jsonb_typeof(approved_permissions) = 'array'",
            name="ck_connector_contract_permissions",
        ),
        sa.CheckConstraint("version > 0", name="ck_connector_contract_version"),
    )
    op.create_index("ix_connector_contracts_org_status", "provider_connector_contracts", ["organization_id", "status"])

    op.create_table(
        "provider_connector_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("acquisition_id", sa.Uuid(), nullable=False),
        sa.Column("form_fingerprint", sa.String(64), nullable=False),
        sa.Column("page_fingerprint", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("allow_full_name", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_phone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_permission_status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("phone_permission_status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "contract_id"],
            ["provider_connector_contracts.organization_id", "provider_connector_contracts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "acquisition_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_connector_bindings_org_id"),
        sa.UniqueConstraint("form_fingerprint", name="uq_connector_bindings_form_global"),
        sa.CheckConstraint("status IN ('draft','active','disabled')", name="ck_connector_binding_status"),
        sa.CheckConstraint(
            "form_fingerprint ~ '^[a-f0-9]{64}$' AND (page_fingerprint IS NULL OR page_fingerprint ~ '^[a-f0-9]{64}$')",
            name="ck_connector_binding_fingerprint",
        ),
        sa.CheckConstraint(
            "email_permission_status IN ('unknown','allowed') AND phone_permission_status IN ('unknown','allowed')",
            name="ck_connector_binding_permission",
        ),
        sa.CheckConstraint("version > 0", name="ck_connector_binding_version"),
    )
    op.create_index("ix_connector_bindings_org_status", "provider_connector_bindings", ["organization_id", "status"])

    op.create_table(
        "connector_ingestions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("lead_fingerprint", sa.String(64), nullable=False),
        sa.Column("lead_reference_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "binding_id"],
            ["provider_connector_bindings.organization_id", "provider_connector_bindings.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_connector_ingestions_org_id"),
        sa.UniqueConstraint("organization_id", "binding_id", "lead_fingerprint", name="uq_connector_ingestions_lead"),
        sa.UniqueConstraint("job_id", name="uq_connector_ingestions_job"),
        sa.CheckConstraint("lead_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_connector_ingestions_fingerprint"),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','quarantined','failed','revoked')",
            name="ck_connector_ingestions_status",
        ),
        sa.CheckConstraint("attempt_count >= 0 AND version > 0", name="ck_connector_ingestions_version"),
    )
    op.create_index(
        "ix_connector_ingestions_org_status", "connector_ingestions", ["organization_id", "status", "received_at"]
    )

    op.create_table(
        "connector_ingestion_outcomes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_id", sa.Uuid(), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("provenance_id", sa.Uuid(), nullable=True),
        sa.Column("result_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "ingestion_id"],
            ["connector_ingestions.organization_id", "connector_ingestions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contact_id"], ["contacts.organization_id", "contacts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "ingestion_id", name="uq_connector_outcomes_ingestion"),
        sa.CheckConstraint(
            "result_code IN ('imported','quarantined','failed','authorization_revoked')",
            name="ck_connector_outcomes_result",
        ),
    )

    for table in (
        "provider_connector_contracts",
        "provider_connector_bindings",
        "connector_ingestions",
        "connector_ingestion_outcomes",
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC")
        op.execute(f"""
            CREATE POLICY {table}_app ON public.{table} FOR ALL TO prospect_app
            USING (organization_id = app_private.current_organization_id())
            WITH CHECK (organization_id = app_private.current_organization_id())
        """)
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO prospect_app")
        op.execute(f"""
            CREATE POLICY {table}_worker ON public.{table} FOR ALL TO prospect_worker
            USING (organization_id = app_private.current_organization_id())
            WITH CHECK (organization_id = app_private.current_organization_id())
        """)
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO prospect_worker")

    op.execute("""
        CREATE FUNCTION app_private.resolve_meta_lead_binding(p_form_fingerprint text)
        RETURNS TABLE(organization_id uuid, binding_id uuid, actor_user_id uuid, actor_membership_id uuid)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, app_private AS $$
          SELECT c.organization_id, b.id, c.reviewed_by, c.reviewer_membership_id
          FROM public.provider_connector_bindings b
          JOIN public.provider_connector_contracts c
            ON c.organization_id = b.organization_id AND c.id = b.contract_id
          JOIN public.source_providers p
            ON p.organization_id = c.organization_id AND p.id = c.provider_id
          JOIN public.acquisition_records a
            ON a.organization_id = b.organization_id AND a.id = b.acquisition_id
          JOIN public.memberships m
            ON m.organization_id = c.organization_id AND m.id = c.reviewer_membership_id
          JOIN public.users u ON u.id = c.reviewed_by
          WHERE b.form_fingerprint = p_form_fingerprint
            AND b.status = 'active' AND c.status = 'approved'
            AND p.status = 'active' AND p.rights_attested_at IS NOT NULL
            AND (p.valid_from IS NULL OR p.valid_from <= clock_timestamp())
            AND (p.valid_until IS NULL OR p.valid_until > clock_timestamp())
            AND a.status = 'approved'
            AND m.status = 'active' AND u.status = 'active'
            AND (c.review_valid_until IS NULL OR c.review_valid_until > clock_timestamp())
        $$
    """)
    op.execute("ALTER FUNCTION app_private.resolve_meta_lead_binding(text) OWNER TO prospect_rls_definer")
    op.execute("REVOKE ALL ON FUNCTION app_private.resolve_meta_lead_binding(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.resolve_meta_lead_binding(text) TO prospect_app")

    # The worker may create only the CRM records produced by an admitted ingestion.
    # Read access was granted in 0023 for exports; it must never modify an existing CRM record.
    for table in ("provenance_records", "prospects", "contacts", "contact_channels", "contact_permissions"):
        op.execute(f"GRANT INSERT ON public.{table} TO prospect_worker")
        op.execute(f"""
            CREATE POLICY {table}_worker_connector_ingest ON public.{table} FOR INSERT TO prospect_worker
            WITH CHECK (organization_id = app_private.current_organization_id())
        """)

    op.execute("""
        CREATE FUNCTION app_private.capture_connector_ingestion_audit() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app_private AS $$
        DECLARE v_action text; v_result text; v_source text;
        BEGIN
          IF TG_OP = 'INSERT' THEN
            v_action := 'connector.ingestion_admitted'; v_result := NULL; v_source := 'api';
          ELSIF NEW.status IS NOT DISTINCT FROM OLD.status OR NEW.status NOT IN ('succeeded','quarantined','failed','revoked') THEN
            RETURN NEW;
          ELSE
            v_action := 'connector.ingestion_completed'; v_source := 'worker';
            v_result := CASE NEW.status WHEN 'succeeded' THEN 'imported' WHEN 'quarantined' THEN 'quarantined'
              WHEN 'failed' THEN 'failed' ELSE 'authorization_revoked' END;
          END IF;
          PERFORM app_private.append_audit_event(
            gen_random_uuid(), 'tenant', NEW.organization_id, 'user', NEW.actor_user_id, v_action,
            'connector_ingestion', NEW.id, current_setting('app.request_id', true),
            current_setting('app.request_id', true), v_source,
            CASE WHEN v_result IS NULL THEN jsonb_build_object('status', NEW.status)
                 ELSE jsonb_build_object('status', NEW.status, 'result_code', v_result) END, 1);
          RETURN NEW;
        END $$
    """)
    op.execute("ALTER FUNCTION app_private.capture_connector_ingestion_audit() OWNER TO prospect_rls_definer")
    op.execute("""
        CREATE TRIGGER capture_connector_ingestion_audit
        AFTER INSERT OR UPDATE OF status ON public.connector_ingestions
        FOR EACH ROW EXECUTE FUNCTION app_private.capture_connector_ingestion_audit()
    """)
    op.execute("""
        CREATE FUNCTION app_private.purge_connector_ingestions(p_limit integer) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app_private AS $$
        DECLARE v_count integer;
        BEGIN
          IF p_limit < 1 OR p_limit > 1000 THEN RAISE EXCEPTION 'invalid_connector_purge_batch'; END IF;
          WITH candidates AS (
            SELECT id FROM public.connector_ingestions
            WHERE purged_at IS NULL AND finished_at < clock_timestamp() - interval '30 days'
            ORDER BY finished_at, id LIMIT p_limit FOR UPDATE SKIP LOCKED
          )
          UPDATE public.connector_ingestions i
          SET lead_reference_ciphertext = '\\x'::bytea, purged_at = clock_timestamp(),
              updated_at = clock_timestamp(), version = version + 1
          FROM candidates WHERE i.id = candidates.id;
          GET DIAGNOSTICS v_count = ROW_COUNT;
          RETURN v_count;
        END $$
    """)
    op.execute("ALTER FUNCTION app_private.purge_connector_ingestions(integer) OWNER TO prospect_rls_definer")
    op.execute("REVOKE ALL ON FUNCTION app_private.purge_connector_ingestions(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.purge_connector_ingestions(integer) TO prospect_worker")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS capture_connector_ingestion_audit ON public.connector_ingestions")
    op.execute("DROP FUNCTION IF EXISTS app_private.capture_connector_ingestion_audit()")
    op.execute("DROP FUNCTION IF EXISTS app_private.purge_connector_ingestions(integer)")
    for table in ("contact_permissions", "contact_channels", "contacts", "prospects", "provenance_records"):
        op.execute(f"DROP POLICY IF EXISTS {table}_worker_connector_ingest ON public.{table}")
        op.execute(f"REVOKE INSERT ON public.{table} FROM prospect_worker")
    op.execute("DROP FUNCTION IF EXISTS app_private.resolve_meta_lead_binding(text)")
    for table in (
        "connector_ingestion_outcomes",
        "connector_ingestions",
        "provider_connector_bindings",
        "provider_connector_contracts",
    ):
        op.drop_table(table)
