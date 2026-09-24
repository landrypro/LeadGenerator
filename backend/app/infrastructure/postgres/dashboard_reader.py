from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from ...application.use_cases.dashboard import DashboardQuery
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork


class PostgresDashboardReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None:
        async with SqlAlchemyTenantUnitOfWork(self._session_factory, context, snapshot_readonly=True) as unit:
            result = await unit.session.execute(
                text("SELECT user_id FROM memberships WHERE organization_id = :org AND id = :owner"),
                {"org": context.organization_id, "owner": membership_id},
            )
            return result.scalar_one_or_none()

    async def read(self, query: DashboardQuery) -> dict[str, list[dict[str, Any]]]:
        context = query.context
        params = {
            "org": context.organization_id,
            "owner": query.owner_membership_id,
            "actor": query.owner_user_id,
            "collective": query.scope == "organization",
            "start_at": query.start_at,
            "observed": query.observed_until,
            "as_of": query.as_of,
            "today_start": query.today_start,
            "today_end": query.today_end,
        }
        statements = {
            "prospects": """
                SELECT owner_id AS owner_membership_id, stage_code, count(*) AS count
                FROM prospects
                WHERE organization_id = :org AND archived_at IS NULL AND created_at <= :as_of
                  AND (:collective OR owner_id = :owner)
                GROUP BY owner_id, stage_code
            """,
            "tasks": """
                SELECT assigned_membership_id AS owner_membership_id,
                  count(*) FILTER (WHERE due_at >= :today_start AND due_at < :today_end) AS due_today,
                  count(*) FILTER (WHERE due_at < :today_start) AS overdue
                FROM prospect_tasks
                WHERE organization_id = :org AND status = 'open' AND created_at <= :as_of
                  AND due_at < :today_end
                  AND (:collective OR assigned_membership_id = :owner)
                GROUP BY assigned_membership_id
            """,
            "activities": """
                WITH RECURSIVE chains AS (
                    SELECT id AS root_id, id, actor_id AS root_actor_id, activity_type,
                           occurred_at, created_at
                    FROM prospect_activities
                    WHERE organization_id = :org AND correction_of_activity_id IS NULL
                      AND created_at <= :as_of
                      AND (:collective OR actor_id = :actor)
                    UNION ALL
                    SELECT chains.root_id, child.id, chains.root_actor_id, child.activity_type,
                           child.occurred_at, child.created_at
                    FROM prospect_activities child
                    JOIN chains ON child.correction_of_activity_id = chains.id
                    WHERE child.organization_id = :org AND child.created_at <= :as_of
                ), active AS (
                    SELECT DISTINCT ON (root_id) root_actor_id, activity_type, occurred_at
                    FROM chains ORDER BY root_id, created_at DESC, id DESC
                )
                SELECT m.id AS owner_membership_id, active.activity_type, count(*) AS count
                FROM active
                LEFT JOIN memberships m ON m.organization_id = :org AND m.user_id = active.root_actor_id
                WHERE active.occurred_at >= :start_at AND active.occurred_at < :observed
                GROUP BY m.id, active.activity_type
            """,
            "stages": """
                WITH entries AS (
                    SELECT p.id AS prospect_id, p.owner_id AS owner_membership_id,
                           'new'::text AS from_stage, p.created_at AS entered_at,
                           1 AS entry_version, p.id AS entry_id
                    FROM prospects p
                    WHERE p.organization_id = :org AND p.created_at >= :start_at
                      AND p.created_at < :observed
                      AND (:collective OR p.owner_id = :owner)
                    UNION ALL
                    SELECT t.prospect_id, p.owner_id, t.to_stage, t.occurred_at,
                           t.resulting_version, t.id
                    FROM prospect_stage_transitions t
                    JOIN prospects p ON p.organization_id = t.organization_id AND p.id = t.prospect_id
                    WHERE t.organization_id = :org AND t.occurred_at >= :start_at
                      AND t.occurred_at < :observed
                      AND (:collective OR p.owner_id = :owner)
                ), first_entries AS (
                    SELECT DISTINCT ON (prospect_id, from_stage) * FROM entries
                    WHERE from_stage IN ('new', 'qualifying', 'qualified', 'contacted',
                                         'opportunity', 'proposal_sent', 'negotiation')
                    ORDER BY prospect_id, from_stage, entered_at, entry_version, entry_id
                )
                SELECT e.owner_membership_id, e.from_stage, exit_transition.to_stage, count(*) AS count
                FROM first_entries e
                LEFT JOIN LATERAL (
                    SELECT t.to_stage FROM prospect_stage_transitions t
                    WHERE t.organization_id = :org AND t.prospect_id = e.prospect_id
                      AND t.from_stage = e.from_stage AND t.from_version >= e.entry_version
                      AND t.occurred_at >= e.entered_at AND t.occurred_at < :observed
                    ORDER BY t.from_version, t.occurred_at, t.id LIMIT 1
                ) exit_transition ON true
                GROUP BY e.owner_membership_id, e.from_stage, exit_transition.to_stage
            """,
            "opportunities": """
                SELECT owner_membership_id, stage_code, currency_code, count(*) AS count,
                       sum(amount) AS amount,
                       sum(round(amount * probability / 100, 4)) AS weighted_amount
                FROM opportunities
                WHERE organization_id = :org AND created_at <= :as_of
                  AND (:collective OR owner_membership_id = :owner)
                GROUP BY owner_membership_id, stage_code, currency_code
            """,
        }
        rows: dict[str, list[dict[str, Any]]] = {}
        async with SqlAlchemyTenantUnitOfWork(self._session_factory, context, snapshot_readonly=True) as unit:
            for name, statement in statements.items():
                result = await unit.session.execute(text(statement), params)
                rows[name] = [dict(row) for row in result.mappings().all()]
        return rows
