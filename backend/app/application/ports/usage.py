from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from ..tenancy import TenantContext


@dataclass(frozen=True, slots=True)
class UsageEvent:
    context: TenantContext
    membership_id: UUID
    operation_id: UUID
    usage_code: str
    event_kind: str
    outcome: str
    occurred_at: datetime
    unit_count: int = 1
    policy_code: str | None = None
    user_limit: int | None = None
    organization_limit: int | None = None
    warning_threshold_percent: int | None = None
    reset_at: datetime | None = None


class UsageStore(Protocol):
    async def record(self, event: UsageEvent) -> None: ...

    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None: ...

    async def report(
        self,
        context: TenantContext,
        *,
        start_on: date,
        end_on: date,
        user_id: UUID | None,
    ) -> dict[str, Any]: ...

    async def audit_report_view(self, context: TenantContext, *, scope: str, start_on: date, end_on: date) -> None: ...


class NullUsageStore:
    async def record(self, event: UsageEvent) -> None:
        del event

    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None:
        del context, membership_id
        return None

    async def report(
        self,
        context: TenantContext,
        *,
        start_on: date,
        end_on: date,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        del context, start_on, end_on, user_id
        return {"rows": [], "last_recorded_at": None}

    async def audit_report_view(self, context: TenantContext, *, scope: str, start_on: date, end_on: date) -> None:
        del context, scope, start_on, end_on
