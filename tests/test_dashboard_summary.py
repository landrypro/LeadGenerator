from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.dashboard import (
    DashboardOwnerNotFound,
    DashboardQuery,
    DashboardValidationError,
    GetDashboardSummaryUseCase,
)

NOW = datetime(2026, 11, 1, 16, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class Reader:
    def __init__(self, owner: UUID, user: UUID) -> None:
        self.owner = owner
        self.user = user
        self.query: DashboardQuery | None = None

    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None:
        return self.user if membership_id == self.owner else None

    async def read(self, query: DashboardQuery) -> dict[str, list[dict[str, object]]]:
        self.query = query
        owner = self.owner
        return {
            "prospects": [
                {"owner_membership_id": owner, "stage_code": "new", "count": 3},
                {"owner_membership_id": None, "stage_code": "qualified", "count": 1},
            ],
            "tasks": [{"owner_membership_id": owner, "due_today": 2, "overdue": 1}],
            "activities": [{"owner_membership_id": owner, "activity_type": "call", "count": 4}],
            "stages": [
                {"owner_membership_id": owner, "from_stage": "new", "to_stage": "qualifying", "count": 2},
                {"owner_membership_id": owner, "from_stage": "new", "to_stage": "lost", "count": 1},
                {"owner_membership_id": owner, "from_stage": "new", "to_stage": None, "count": 2},
            ],
            "opportunities": [
                {
                    "owner_membership_id": owner,
                    "stage_code": "proposal",
                    "currency_code": "CAD",
                    "count": 1,
                    "amount": Decimal("1000.0000"),
                    "weighted_amount": Decimal("500.0000"),
                },
                {
                    "owner_membership_id": owner,
                    "stage_code": "negotiation",
                    "currency_code": "USD",
                    "count": 1,
                    "amount": Decimal("2000.0000"),
                    "weighted_amount": Decimal("500.0000"),
                },
                {
                    "owner_membership_id": owner,
                    "stage_code": "lost",
                    "currency_code": "CAD",
                    "count": 1,
                    "amount": Decimal("100.0000"),
                    "weighted_amount": Decimal("0.0000"),
                },
            ],
        }


def fixture() -> tuple[GetDashboardSummaryUseCase, Reader, TenantContext, UUID]:
    user, owner, org = uuid4(), uuid4(), uuid4()
    reader = Reader(owner, user)
    return GetDashboardSummaryUseCase(reader, FixedClock()), reader, TenantContext(user, org, "dashboard-test"), owner


async def execute(
    use_case: GetDashboardSummaryUseCase, context: TenantContext, membership_id: UUID, **overrides: object
) -> dict[str, object]:
    arguments: dict[str, object] = {
        "context": context,
        "membership_id": membership_id,
        "timezone": "America/Toronto",
        "scope": "self",
        "owner_membership_id": None,
        "period": "day",
        "start_on": None,
        "end_on": None,
        "can_read_self": True,
        "can_read_organization": False,
    }
    arguments.update(overrides)
    return await use_case.execute(**arguments)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_dashboard_uses_local_dst_boundaries_and_separate_currency_totals() -> None:
    use_case, reader, context, owner = fixture()
    result = await execute(use_case, context, owner)
    assert result["period"] == {
        "start_on": "2026-11-01",
        "end_on": "2026-11-01",
        "timezone": "America/Toronto",
        "start_at_utc": "2026-11-01T04:00:00Z",
        "end_at_utc_exclusive": "2026-11-02T05:00:00Z",
    }
    assert reader.query is not None and (reader.query.today_end - reader.query.today_start).total_seconds() == 25 * 3600
    assert result["prospects_by_stage"][0] == {"stage_code": "new", "count": 3}  # type: ignore[index]
    assert result["tasks"] == {"due_today": 2, "overdue": 1}
    assert result["stage_passage"][0]["rate_percent"] == "40.00"  # type: ignore[index]
    assert result["stage_losses"][0]["lost"] == 1  # type: ignore[index]
    assert result["pipeline_by_currency"] == [
        {"currency_code": "CAD", "amount": "1000.0000", "weighted_amount": "500.0000"},
        {"currency_code": "USD", "amount": "2000.0000", "weighted_amount": "500.0000"},
    ]
    assert result["google_usage"]["used"] is None  # type: ignore[index]


@pytest.mark.asyncio
async def test_dashboard_organization_reconciles_unassigned_and_owner_rows() -> None:
    use_case, _, context, owner = fixture()
    result = await execute(use_case, context, owner, scope="organization", can_read_organization=True)
    assert result["prospects_by_stage"][0]["count"] == 3  # type: ignore[index]
    assert result["prospects_by_stage"][2]["count"] == 1  # type: ignore[index]
    rows = result["owner_breakdown"]
    assert len(rows) == 2  # type: ignore[arg-type]
    assert {item["owner_membership_id"] for item in rows} == {str(owner), None}  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_dashboard_rejects_other_owner_and_bad_period_before_read() -> None:
    use_case, reader, context, owner = fixture()
    with pytest.raises(PermissionError):
        await execute(use_case, context, owner, scope="organization")
    with pytest.raises(DashboardValidationError) as invalid:
        await execute(use_case, context, owner, period="month", start_on="2026-10-01", end_on="2026-10-31")
    assert invalid.value.field == "period"
    with pytest.raises(DashboardValidationError) as too_long:
        await execute(use_case, context, owner, period=None, start_on="2026-01-01", end_on="2026-06-01")
    assert too_long.value.field == "end_on"
    with pytest.raises(DashboardValidationError) as malformed:
        await execute(use_case, context, owner, period=None, start_on="20260901", end_on="2026-09-23")
    assert malformed.value.field == "start_on"
    with pytest.raises(DashboardValidationError) as future:
        await execute(use_case, context, owner, period=None, start_on="2026-11-02", end_on="2026-11-02")
    assert future.value.field == "start_on"
    with pytest.raises(DashboardOwnerNotFound):
        await execute(use_case, context, owner, scope="owner", owner_membership_id=uuid4(), can_read_organization=True)
    assert reader.query is None
