from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.app.application.models import GoogleAccessOwner, GoogleQuotaReservation, GoogleSearchQuotaPolicy
from backend.app.application.ports.usage import UsageEvent
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.usage import (
    GetCurrentUsageUseCase,
    GetUsageReportUseCase,
    UsageOwnerNotFound,
    UsageValidationError,
)

NOW = datetime(2026, 9, 24, 15, tzinfo=UTC)


class Clock:
    def now(self) -> datetime:
        return NOW


class Store:
    def __init__(self, owner: UUID | None = None) -> None:
        self.owner = owner
        self.queries: list[UUID | None] = []
        self.audits: list[tuple[str, date, date]] = []

    async def record(self, event: UsageEvent) -> None:
        del event

    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None:
        del context, membership_id
        return self.owner

    async def report(
        self, context: TenantContext, *, start_on: date, end_on: date, user_id: UUID | None
    ) -> dict[str, Any]:
        del context, start_on, end_on
        self.queries.append(user_id)
        multiplier = 1 if user_id else 2
        return {
            "rows": [
                {
                    "usage_day": date(2026, 9, 24),
                    "usage_code": "google.places_text_search.quota",
                    "event_kind": "quota_reserved",
                    "outcome": "accepted",
                    "unit_count": 3 * multiplier,
                    "row_count": 0,
                    "created_count": 0,
                    "duplicate_count": 0,
                    "review_count": 0,
                    "quarantined_count": 0,
                    "omitted_count": 0,
                    "byte_count": 0,
                    "last_recorded_at": NOW,
                }
            ],
            "last_recorded_at": NOW,
        }

    async def audit_report_view(self, context: TenantContext, *, scope: str, start_on: date, end_on: date) -> None:
        del context
        self.audits.append((scope, start_on, end_on))


class Policy:
    async def resolve(self, owner: GoogleAccessOwner) -> GoogleSearchQuotaPolicy:
        del owner
        return GoogleSearchQuotaPolicy(True, 20, 100, 80, "server_default_v1")


class Quota:
    async def reserve(self, *args: object, **kwargs: object) -> GoogleQuotaReservation:
        raise AssertionError("reserve is not used")

    async def current(
        self, owner: GoogleAccessOwner, policy: GoogleSearchQuotaPolicy, *, now: datetime
    ) -> GoogleQuotaReservation:
        del owner, now
        return GoogleQuotaReservation(True, None, 4, 16, 12, 88, NOW, 60, policy.policy_code)


@pytest.mark.asyncio
async def test_report_exposes_qualified_google_units_and_utc_period() -> None:
    actor, organization, membership = uuid4(), uuid4(), uuid4()
    result = await GetUsageReportUseCase(Store(), Clock()).execute(
        context=TenantContext(actor, organization, "usage-report"),
        membership_id=membership,
        scope="self",
        owner_membership_id=None,
        period="today",
        start_on=None,
        end_on=None,
        group_by="day",
        can_read_self=True,
        can_read_organization=False,
    )
    quota = result["google"]["totals"][0]
    assert quota == {
        "code": "google.places_text_search.quota",
        "unit": "reservation",
        "accepted": 3,
        "rejected": 0,
    }
    assert result["period"]["timezone"] == "UTC"
    assert result["google"]["billing"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_organization_report_is_audited_but_self_report_is_not() -> None:
    actor, organization, membership = uuid4(), uuid4(), uuid4()
    store = Store()
    use_case = GetUsageReportUseCase(store, Clock())
    common = {
        "context": TenantContext(actor, organization, "usage-report-audit"),
        "membership_id": membership,
        "owner_membership_id": None,
        "period": "today",
        "start_on": None,
        "end_on": None,
        "group_by": "day",
        "can_read_self": True,
        "can_read_organization": True,
    }
    await use_case.execute(scope="self", **common)
    await use_case.execute(scope="organization", **common)
    assert store.audits == [("organization", NOW.date(), NOW.date())]


@pytest.mark.asyncio
async def test_report_rejects_invalid_scope_and_hides_unknown_owner() -> None:
    context = TenantContext(uuid4(), uuid4(), "usage-report")
    use_case = GetUsageReportUseCase(Store(), Clock())
    with pytest.raises(PermissionError):
        await use_case.execute(
            context=context,
            membership_id=uuid4(),
            scope="organization",
            owner_membership_id=None,
            period="today",
            start_on=None,
            end_on=None,
            group_by="day",
            can_read_self=True,
            can_read_organization=False,
        )
    with pytest.raises(UsageOwnerNotFound):
        await use_case.execute(
            context=context,
            membership_id=uuid4(),
            scope="owner",
            owner_membership_id=uuid4(),
            period="today",
            start_on=None,
            end_on=None,
            group_by="day",
            can_read_self=True,
            can_read_organization=True,
        )
    with pytest.raises(UsageValidationError):
        await use_case.execute(
            context=context,
            membership_id=uuid4(),
            scope="self",
            owner_membership_id=None,
            period="custom",
            start_on="2026-01-01",
            end_on="2026-09-24",
            group_by="day",
            can_read_self=True,
            can_read_organization=False,
        )


@pytest.mark.asyncio
async def test_current_uses_redis_for_enforcement_and_keeps_both_scopes() -> None:
    actor, organization = uuid4(), uuid4()
    result = await GetCurrentUsageUseCase(Store(), Quota(), Policy(), Clock()).execute(
        context=TenantContext(actor, organization, "usage-current"),
        scope="self",
        can_read_self=True,
        can_read_organization=False,
    )
    assert result["used"] == 4
    assert result["source"] == "redis_quota"
    assert result["user"] == {"used": 4, "remaining": 16, "limit": 20}
    assert result["organization"] == {"used": 12, "remaining": 88, "limit": 100}
