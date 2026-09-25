from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.audit_events import tenant_audit_event
from ...application.errors import UsageReportUnavailable, UsageTrackingUnavailable
from ...application.ports.metrics import MetricsRecorder, NullMetricsRecorder, UsageApi
from ...application.ports.usage import UsageEvent
from ...application.tenancy import TenantContext
from ...domain.audit import AuditAction
from .audit_recorder import SqlAlchemyAuditRecorder
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork


class PostgresUsageStore:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], metrics: MetricsRecorder | None = None
    ) -> None:
        self._sessions = session_factory
        self._metrics = metrics or NullMetricsRecorder()

    async def record(self, event: UsageEvent) -> None:
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, event.context) as unit:
                await unit.session.execute(
                    text("""
                    SELECT app_private.record_usage_event(
                        :membership, :operation, :code, :kind, :outcome, :occurred,
                        :units, :policy, :user_limit, :organization_limit, :warning, :reset_at,
                        NULL, NULL, NULL, NULL, NULL, NULL, NULL
                    )
                """),
                    {
                        "membership": event.membership_id,
                        "operation": event.operation_id,
                        "code": event.usage_code,
                        "kind": event.event_kind,
                        "outcome": event.outcome,
                        "occurred": event.occurred_at,
                        "units": event.unit_count,
                        "policy": event.policy_code,
                        "user_limit": event.user_limit,
                        "organization_limit": event.organization_limit,
                        "warning": event.warning_threshold_percent,
                        "reset_at": event.reset_at,
                    },
                )
                await unit.commit()
            self._metrics.record_usage_registry_write(
                _metric_api(event.usage_code), "accepted", event.policy_code or "none"
            )
        except SQLAlchemyError as error:
            self._metrics.record_usage_registry_write(
                _metric_api(event.usage_code), "failed", event.policy_code or "none"
            )
            raise UsageTrackingUnavailable from error

    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None:
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                result = await unit.session.execute(
                    text("SELECT user_id FROM memberships WHERE organization_id = :org AND id = :membership"),
                    {"org": context.organization_id, "membership": membership_id},
                )
                return result.scalar_one_or_none()
        except SQLAlchemyError as error:
            raise UsageReportUnavailable from error

    async def report(
        self,
        context: TenantContext,
        *,
        start_on: date,
        end_on: date,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context, snapshot_readonly=True) as unit:
                result = await unit.session.execute(
                    text("""
                    SELECT usage_day, usage_code, event_kind, outcome,
                           sum(unit_count)::bigint AS unit_count,
                           sum(row_count)::bigint AS row_count,
                           sum(created_count)::bigint AS created_count,
                           sum(duplicate_count)::bigint AS duplicate_count,
                           sum(review_count)::bigint AS review_count,
                           sum(quarantined_count)::bigint AS quarantined_count,
                           sum(omitted_count)::bigint AS omitted_count,
                           sum(byte_count)::bigint AS byte_count,
                           max(last_recorded_at) AS last_recorded_at
                    FROM usage_daily_counters
                    WHERE organization_id = :org AND usage_day BETWEEN :start_on AND :end_on
                      AND actor_user_id IS NOT DISTINCT FROM CAST(:user_id AS uuid)
                    GROUP BY usage_day, usage_code, event_kind, outcome
                    ORDER BY usage_day, usage_code, event_kind, outcome
                """),
                    {"org": context.organization_id, "start_on": start_on, "end_on": end_on, "user_id": user_id},
                )
                rows = [dict(row) for row in result.mappings().all()]
                owner_rows: list[dict[str, Any]] = []
                if user_id is None:
                    breakdown = await unit.session.execute(
                        text("""
                            SELECT m.id AS owner_membership_id, c.usage_code, c.event_kind, c.outcome,
                                   sum(c.unit_count)::bigint AS unit_count
                            FROM usage_daily_counters c
                            JOIN memberships m ON m.organization_id = c.organization_id
                                              AND m.user_id = c.actor_user_id
                            WHERE c.organization_id = :org
                              AND c.usage_day BETWEEN :start_on AND :end_on
                              AND c.actor_user_id IS NOT NULL
                            GROUP BY m.id, c.usage_code, c.event_kind, c.outcome
                            ORDER BY m.id, c.usage_code, c.event_kind, c.outcome
                        """),
                        {"org": context.organization_id, "start_on": start_on, "end_on": end_on},
                    )
                    owner_rows = [dict(row) for row in breakdown.mappings().all()]
        except SQLAlchemyError as error:
            raise UsageReportUnavailable from error
        return {
            "rows": rows,
            "last_recorded_at": max((row["last_recorded_at"] for row in rows), default=None),
            "owner_rows": owner_rows,
        }

    async def audit_report_view(self, context: TenantContext, *, scope: str, start_on: date, end_on: date) -> None:
        try:
            async with SqlAlchemyTenantUnitOfWork(self._sessions, context) as unit:
                await SqlAlchemyAuditRecorder(unit.session).record(
                    tenant_audit_event(
                        context,
                        AuditAction.USAGE_REPORT_VIEWED,
                        context.organization_id,
                        {
                            "scope": scope,
                            "start_on": start_on.isoformat(),
                            "end_on": end_on.isoformat(),
                            "group_by": "day",
                        },
                    )
                )
                await unit.commit()
        except SQLAlchemyError as error:
            raise UsageReportUnavailable from error


def _metric_api(usage_code: str) -> UsageApi:
    values: dict[str, UsageApi] = {
        "google.places_text_search.quota": "places_text_search_quota",
        "google.places_text_search.request": "places_text_search",
        "google.places_autocomplete.request": "places_autocomplete",
        "google.places_details.request": "places_details",
        "google.maps_static.request": "maps_static",
        "platform.csv_export": "csv_export",
        "platform.csv_import": "csv_import",
    }
    return values.get(usage_code, "places_text_search")
