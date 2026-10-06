"""Expose a guarded organization-level Automation settings command.

The settings table remains read-only to the application role.  The command is
implemented as a small SECURITY DEFINER function so the API can perform the
same audited, tenant-bound operation as the existing Automation commands
without granting table-wide INSERT/UPDATE privileges.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261006_0040"
down_revision: str | None = "20261005_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SIGNATURE = "app_private.set_automation_organization_settings(boolean,integer,text)"


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION app_private.set_automation_organization_settings(
          p_automation_enabled boolean,
          p_expected_version integer,
          p_request_id text
        ) RETURNS jsonb
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
        DECLARE
          v_org uuid := app_private.current_organization_id();
          v_actor uuid := app_private.current_actor_id();
          v_existing public.automation_organization_settings%ROWTYPE;
          v_now timestamptz := pg_catalog.clock_timestamp();
          v_new_version integer;
          v_generation integer;
          v_previous_enabled boolean;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_request_id IS NULL OR p_expected_version < 0 THEN
            RETURN jsonb_build_object('code', 'invalid_contract');
          END IF;
          IF NOT EXISTS (
            SELECT 1
            FROM public.users AS u
            JOIN public.memberships AS m ON m.user_id = u.id
            JOIN public.organizations AS o ON o.id = m.organization_id
            WHERE u.id = v_actor AND u.status = 'active'
              AND m.organization_id = v_org AND m.status = 'active' AND m.role = 'admin'
              AND o.status = 'active'
          ) THEN
            RETURN jsonb_build_object('code', 'forbidden');
          END IF;

          SELECT * INTO v_existing
          FROM public.automation_organization_settings
          WHERE organization_id = v_org
          FOR UPDATE;

          IF NOT FOUND THEN
            IF p_expected_version <> 0 THEN
              RETURN jsonb_build_object('code', 'version_conflict', 'current_version', 0);
            END IF;
            INSERT INTO public.automation_organization_settings (
              id, organization_id, automation_enabled, suspension_generation,
              created_at, updated_at, version
            ) VALUES (
              pg_catalog.gen_random_uuid(), v_org, p_automation_enabled, 0,
              v_now, v_now, 1
            )
            RETURNING * INTO v_existing;
            v_previous_enabled := false;
            v_new_version := 1;
            v_generation := 0;
          ELSE
            IF p_expected_version <> v_existing.version THEN
              RETURN jsonb_build_object('code', 'version_conflict', 'current_version', v_existing.version);
            END IF;
            IF v_existing.automation_enabled = p_automation_enabled THEN
              RETURN jsonb_build_object(
                'code', 'completed', 'id', v_existing.id, 'automation_enabled', v_existing.automation_enabled,
                'suspension_generation', v_existing.suspension_generation, 'version', v_existing.version,
                'replayed', true
              );
            END IF;
            v_previous_enabled := v_existing.automation_enabled;
            v_generation := v_existing.suspension_generation
              + CASE WHEN v_existing.automation_enabled AND NOT p_automation_enabled THEN 1 ELSE 0 END;
            v_new_version := v_existing.version + 1;
            UPDATE public.automation_organization_settings
            SET automation_enabled = p_automation_enabled,
                suspension_generation = v_generation,
                updated_at = v_now,
                version = v_new_version
            WHERE organization_id = v_org;
          END IF;

          PERFORM app_private.append_audit_event(
            pg_catalog.gen_random_uuid(), 'tenant', v_org, 'user', v_actor,
            'automation.organization_settings_changed', 'automation_organization_settings',
            v_existing.id, p_request_id, p_request_id, 'api',
            pg_catalog.jsonb_build_object(
              'previous_enabled', v_previous_enabled,
              'new_enabled', p_automation_enabled,
              'previous_version', CASE WHEN v_existing.version = v_new_version THEN 0 ELSE v_existing.version END,
              'new_version', v_new_version,
              'suspension_generation', v_generation
            ),
            1::smallint
          );
          RETURN jsonb_build_object(
            'code', 'completed', 'id', v_existing.id, 'automation_enabled', p_automation_enabled,
            'suspension_generation', v_generation, 'version', v_new_version, 'replayed', false
          );
        END
        $function$
        """
    )
    op.execute(f"ALTER FUNCTION {_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_SIGNATURE} TO prospect_app")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_SIGNATURE} FROM prospect_app")
    op.execute(f"DROP FUNCTION {_SIGNATURE}")
