"""Lectures Automation minimisées, isolées par organisation et sans effet métier."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork


class AutomationReadUnavailable(RuntimeError):
    """Les projections Automation ne sont pas consultables de façon sûre."""


class AutomationReadCursorInvalid(ValueError):
    """Le curseur ne désigne pas une ressource visible dans le tenant."""


class AutomationReader:
    """Expose seulement les projections nécessaires à AUT-COR-03.

    Les requêtes utilisent la transaction RLS du tenant et ne déclenchent aucun
    Prévol, job, changement CRM ni écriture d'audit.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_playbooks(
        self,
        context: TenantContext,
        *,
        organization_scope: bool,
        membership_id: UUID | None = None,
        limit: int,
        cursor: UUID | None,
    ) -> dict[str, Any]:
        # La configuration d'un Playbook est une donnée d'organisation. Les
        # commerciaux obtiennent le catalogue local côté client, sans révéler
        # l'état, les versions ni les Prévols de leur organisation. Les
        # volumes CRM restent toutefois visibles car ils sont une projection
        # de lecture, non une configuration Automation.
        try:
            live_scopes = await self.live_playbook_scopes(
                context, membership_id=membership_id or context.actor_id, organization_scope=organization_scope
            )
            if not organization_scope:
                return {"items": [], "next_cursor": None, "live_scopes": live_scopes}
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                anchor = await self._anchor(unit.session, "automation_playbooks", cursor) if cursor else None
                rows = (
                    (
                        await unit.session.execute(
                            text(
                                """
                            SELECT p.id, p.code, p.state, p.prepare_enabled, p.suspension_generation,
                                   p.version, p.created_at, p.updated_at,
                                   latest.version_number AS active_version,
                                   latest.ruleset_version,
                                   latest_preflight.id AS latest_preflight_id,
                                   latest_preflight.state AS latest_preflight_state,
                                   latest_preflight.expires_at AS latest_preflight_expires_at
                            FROM automation_playbooks p
                            LEFT JOIN LATERAL (
                              SELECT version_number, ruleset_version
                              FROM automation_playbook_versions v
                              WHERE v.organization_id = p.organization_id AND v.playbook_id = p.id
                              ORDER BY v.version_number DESC, v.created_at DESC, v.id DESC LIMIT 1
                            ) latest ON true
                            LEFT JOIN LATERAL (
                              SELECT f.id, f.state, f.expires_at
                              FROM automation_preflights f
                              JOIN automation_playbook_versions v ON v.id = f.playbook_version_id
                              WHERE f.organization_id = p.organization_id AND v.playbook_id = p.id
                              ORDER BY f.created_at DESC, f.id DESC LIMIT 1
                            ) latest_preflight ON true
                            WHERE (CAST(:anchor_at AS timestamptz) IS NULL
                                   OR (p.created_at, p.id) < (CAST(:anchor_at AS timestamptz), CAST(:anchor_id AS uuid)))
                            ORDER BY p.created_at DESC, p.id DESC
                            LIMIT :limit
                            """
                            ),
                            {
                                "anchor_at": anchor[0] if anchor else None,
                                "anchor_id": cursor,
                                "limit": limit + 1,
                            },
                        )
                    )
                    .mappings()
                    .all()
                )
        except SQLAlchemyError as error:
            raise AutomationReadUnavailable from error
        page = _page(rows, limit)
        page["live_scopes"] = live_scopes
        return page

    async def get_today(
        self,
        context: TenantContext,
        *,
        membership_id: UUID,
        organization_scope: bool,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Read-only projection of the CRM objects that merit attention today."""
        scope = "(:organization_scope OR p.owner_id = :membership_id)"
        task_scope = "(:organization_scope OR t.assigned_membership_id = :membership_id)"
        opportunity_scope = "(:organization_scope OR o.owner_membership_id = :membership_id)"
        params = {
            "organization_scope": organization_scope,
            "membership_id": membership_id,
            "limit": limit,
        }
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                counts = (
                    (
                        await unit.session.execute(
                            text(
                                f"""
                            SELECT
                              (SELECT count(*) FROM prospects p
                               WHERE p.archived_at IS NULL
                                 AND p.stage_code NOT IN ('won', 'lost', 'archived')
                                 AND {scope}) AS open_prospects,
                              (SELECT count(*) FROM prospect_tasks t
                               JOIN prospects p ON p.organization_id = t.organization_id AND p.id = t.prospect_id
                               WHERE t.status = 'open' AND t.due_at <= CURRENT_TIMESTAMP
                                 AND p.archived_at IS NULL AND {task_scope}) AS due_tasks,
                              (SELECT count(*) FROM prospect_tasks t
                               JOIN prospects p ON p.organization_id = t.organization_id AND p.id = t.prospect_id
                               WHERE t.status = 'open' AND t.due_at < CURRENT_TIMESTAMP
                                 AND p.archived_at IS NULL AND {task_scope}) AS overdue_tasks,
                              (SELECT count(*) FROM opportunities o
                               JOIN prospects p ON p.organization_id = o.organization_id AND p.id = o.prospect_id
                               WHERE o.stage_code NOT IN ('won', 'lost')
                                 AND p.archived_at IS NULL AND {opportunity_scope}) AS open_opportunities
                            """
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .one()
                )
                task_rows = (
                    (
                        await unit.session.execute(
                            text(
                                f"""
                                SELECT t.id, t.title AS label, t.priority, t.due_at,
                                       p.id AS prospect_id, p.internal_alias AS prospect_label,
                                       'task' AS kind, 'open' AS stage
                                FROM prospect_tasks t
                                JOIN prospects p ON p.organization_id = t.organization_id AND p.id = t.prospect_id
                                WHERE t.status = 'open' AND p.archived_at IS NULL AND {task_scope}
                                ORDER BY t.due_at ASC, t.priority DESC, t.id
                                LIMIT :limit
                                """
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .all()
                )
                prospect_rows = (
                    (
                        await unit.session.execute(
                            text(
                                f"""
                                SELECT p.id, p.internal_alias AS label, p.priority, p.updated_at,
                                       p.stage_code AS stage, 'prospect' AS kind
                                FROM prospects p
                                WHERE p.archived_at IS NULL
                                  AND p.stage_code NOT IN ('won', 'lost', 'archived')
                                  AND {scope}
                                ORDER BY p.priority DESC, p.updated_at DESC, p.id
                                LIMIT :limit
                                """
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .all()
                )
                opportunity_rows = (
                    (
                        await unit.session.execute(
                            text(
                                f"""
                                SELECT o.id, o.name AS label, o.stage_code AS stage,
                                       o.expected_close_on, p.internal_alias AS prospect_label,
                                       'opportunity' AS kind
                                FROM opportunities o
                                JOIN prospects p ON p.organization_id = o.organization_id AND p.id = o.prospect_id
                                WHERE o.stage_code NOT IN ('won', 'lost')
                                  AND p.archived_at IS NULL AND {opportunity_scope}
                                ORDER BY o.expected_close_on ASC, o.updated_at DESC, o.id
                                LIMIT :limit
                                """
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .all()
                )
        except SQLAlchemyError as error:
            raise AutomationReadUnavailable from error

        items = [dict(row) for row in (*task_rows, *prospect_rows, *opportunity_rows)]
        items.sort(
            key=lambda item: (
                str(item.get("due_at") or item.get("expected_close_on") or item.get("updated_at") or ""),
                item["kind"],
            )
        )
        return {
            "counts": {
                key: int(counts[key] or 0)
                for key in ("open_prospects", "due_tasks", "overdue_tasks", "open_opportunities")
            },
            "items": items[:limit],
        }

    async def live_playbook_scopes(
        self, context: TenantContext, *, membership_id: UUID, organization_scope: bool
    ) -> dict[str, dict[str, int]]:
        """Return counts from canonical CRM tables without creating playbook rows."""
        prospect_scope = "(:organization_scope OR p.owner_id = :membership_id)"
        opportunity_scope = "(:organization_scope OR o.owner_membership_id = :membership_id)"
        params = {"organization_scope": organization_scope, "membership_id": membership_id}
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                row = (
                    (
                        await unit.session.execute(
                            text(
                                f"""
                            SELECT
                              (SELECT count(*) FROM prospects p
                               WHERE p.archived_at IS NULL AND p.stage_code = 'new' AND {prospect_scope}) AS new_prospect,
                              (SELECT count(*) FROM opportunities o
                               JOIN prospects p ON p.organization_id = o.organization_id AND p.id = o.prospect_id
                               WHERE o.stage_code = 'proposal' AND p.archived_at IS NULL AND {opportunity_scope}) AS proposal_pending,
                              (SELECT count(*) FROM opportunities o
                               JOIN prospects p ON p.organization_id = o.organization_id AND p.id = o.prospect_id
                               WHERE o.stage_code IN ('discovery', 'qualification', 'proposal', 'negotiation')
                                 AND p.archived_at IS NULL AND {opportunity_scope}
                                 AND NOT EXISTS (
                                   SELECT 1 FROM prospect_activities a
                                   WHERE a.organization_id = o.organization_id AND a.prospect_id = o.prospect_id
                                     AND a.occurred_at >= CURRENT_TIMESTAMP - INTERVAL '14 days'
                                 )
                                 AND NOT EXISTS (
                                   SELECT 1 FROM prospect_tasks t
                                   WHERE t.organization_id = o.organization_id AND t.prospect_id = o.prospect_id
                                     AND t.status = 'open'
                                 )) AS forgotten_opportunity
                            """
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .one()
                )
        except SQLAlchemyError as error:
            raise AutomationReadUnavailable from error
        return {
            code: {"subject_count": int(row[code] or 0)}
            for code in ("new_prospect", "proposal_pending", "forgotten_opportunity")
        }

    async def get_playbook(
        self, context: TenantContext, *, code: str, organization_scope: bool, membership_id: UUID | None = None
    ) -> dict[str, Any] | None:
        page = await self.list_playbooks(
            context, organization_scope=organization_scope, membership_id=membership_id, limit=100, cursor=None
        )
        return next((item for item in page["items"] if item["code"] == code), None)

    async def list_exceptions(
        self,
        context: TenantContext,
        *,
        membership_id: UUID,
        organization_scope: bool,
        state: str | None,
        limit: int,
        cursor: UUID | None,
    ) -> dict[str, Any]:
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                anchor = await self._anchor(unit.session, "automation_exceptions", cursor) if cursor else None
                rows = (
                    (
                        await unit.session.execute(
                            text(
                                """
                            SELECT e.id, e.decision_id, e.subject_type, e.subject_id, e.exception_code,
                                   e.state, e.assigned_membership_id, e.resolution_code, e.version,
                                   COALESCE(pr.internal_alias, op.name) AS subject_label,
                                   COALESCE(pr.stage_code, op.stage_code) AS subject_stage,
                                   e.created_at, e.updated_at
                            FROM automation_exceptions e
                            LEFT JOIN prospects pr ON e.subject_type = 'prospect'
                              AND pr.organization_id = e.organization_id AND pr.id = e.subject_id
                            LEFT JOIN opportunities op ON e.subject_type = 'opportunity'
                              AND op.organization_id = e.organization_id AND op.id = e.subject_id
                            WHERE (:organization_scope OR e.assigned_membership_id = :membership_id
                                   OR (e.state = 'open' AND e.assigned_membership_id IS NULL))
                              AND (CAST(:state AS text) IS NULL OR e.state = CAST(:state AS text))
                              AND (CAST(:anchor_at AS timestamptz) IS NULL
                                   OR (e.created_at, e.id) < (CAST(:anchor_at AS timestamptz), CAST(:anchor_id AS uuid)))
                            ORDER BY e.created_at DESC, e.id DESC
                            LIMIT :limit
                            """
                            ),
                            {
                                "organization_scope": organization_scope,
                                "membership_id": membership_id,
                                "state": state,
                                "anchor_at": anchor[0] if anchor else None,
                                "anchor_id": cursor,
                                "limit": limit + 1,
                            },
                        )
                    )
                    .mappings()
                    .all()
                )
        except SQLAlchemyError as error:
            raise AutomationReadUnavailable from error
        return _page(rows, limit)

    async def get_exception(
        self,
        context: TenantContext,
        *,
        exception_id: UUID,
        membership_id: UUID,
        organization_scope: bool,
    ) -> dict[str, Any] | None:
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                row = (
                    (
                        await unit.session.execute(
                            text(
                                """
                            SELECT e.id, e.decision_id, e.subject_type, e.subject_id, e.exception_code, e.state,
                                   e.assigned_membership_id, e.resolution_code, e.version,
                                   COALESCE(pr.internal_alias, op.name) AS subject_label,
                                   COALESCE(pr.stage_code, op.stage_code) AS subject_stage,
                                   e.created_at, e.updated_at
                            FROM automation_exceptions e
                            LEFT JOIN prospects pr ON e.subject_type = 'prospect'
                              AND pr.organization_id = e.organization_id AND pr.id = e.subject_id
                            LEFT JOIN opportunities op ON e.subject_type = 'opportunity'
                              AND op.organization_id = e.organization_id AND op.id = e.subject_id
                            WHERE e.id = :id
                              AND (:organization_scope OR e.assigned_membership_id = :membership_id
                                   OR (e.state = 'open' AND e.assigned_membership_id IS NULL))
                            """
                            ),
                            {
                                "id": exception_id,
                                "membership_id": membership_id,
                                "organization_scope": organization_scope,
                            },
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
        except SQLAlchemyError as error:
            raise AutomationReadUnavailable from error
        return dict(row) if row else None

    async def get_preflight(
        self,
        context: TenantContext,
        *,
        preflight_id: UUID,
        membership_id: UUID,
        organization_scope: bool,
    ) -> dict[str, Any] | None:
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                row = (
                    (
                        await unit.session.execute(
                            text(
                                """
                            SELECT f.id, p.code AS playbook_code, f.ruleset_version, f.scope_fingerprint, f.state,
                                   f.correlation_id, f.subject_count, f.green_count, f.yellow_count,
                                   f.red_count, f.to_verify_count, f.created_at, f.updated_at, f.expires_at
                            FROM automation_preflights f
                            JOIN automation_playbook_versions v ON v.id = f.playbook_version_id
                            JOIN automation_playbooks p ON p.id = v.playbook_id
                            WHERE f.id = :id
                              AND (:organization_scope OR f.requested_by_membership_id = :membership_id)
                            """
                            ),
                            {
                                "id": preflight_id,
                                "membership_id": membership_id,
                                "organization_scope": organization_scope,
                            },
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
        except SQLAlchemyError as error:
            raise AutomationReadUnavailable from error
        return dict(row) if row else None

    @staticmethod
    async def _anchor(session: AsyncSession, table: str, cursor: UUID) -> tuple[datetime]:
        # Le nom de table appartient à un ensemble fermé contrôlé par ce lecteur.
        if table not in {"automation_playbooks", "automation_exceptions"}:
            raise AssertionError("table d'ancrage Automation invalide")
        value = (
            await session.execute(text(f"SELECT created_at FROM {table} WHERE id = :id"), {"id": cursor})
        ).scalar_one_or_none()
        if value is None:
            raise AutomationReadCursorInvalid
        return (value,)


def _page(rows: Any, limit: int) -> dict[str, Any]:
    items = [dict(row) for row in rows[:limit]]
    return {"items": items, "next_cursor": str(items[-1]["id"]) if len(rows) > limit else None}
