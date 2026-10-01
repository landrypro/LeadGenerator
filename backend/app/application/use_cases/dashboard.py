from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from ..ports.clock import Clock
from ..ports.usage import UsageStore
from ..tenancy import TenantContext

STAGES = ("new", "qualifying", "qualified", "contacted", "opportunity", "proposal_sent", "negotiation", "won", "lost")
PASSAGES = (
    ("new", "qualifying"),
    ("qualifying", "qualified"),
    ("qualified", "contacted"),
    ("contacted", "opportunity"),
    ("opportunity", "proposal_sent"),
    ("proposal_sent", "negotiation"),
    ("proposal_sent", "won"),
    ("negotiation", "won"),
)
LOSS_STAGES = tuple(dict.fromkeys(start for start, _ in PASSAGES))
ACTIVITY_TYPES = ("call", "meeting", "email", "note")
MAX_DAYS = 93


class DashboardValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class DashboardOwnerNotFound(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DashboardQuery:
    context: TenantContext
    scope: str
    owner_membership_id: UUID | None
    owner_user_id: UUID | None
    start_at: datetime
    end_at: datetime
    observed_until: datetime
    today_start: datetime
    today_end: datetime
    as_of: datetime


class DashboardReader(Protocol):
    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None: ...

    async def read(self, query: DashboardQuery) -> dict[str, list[dict[str, Any]]]: ...


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _period_dates(period: str | None, start_on: str | None, end_on: str | None, today: date) -> tuple[date, date]:
    if period is not None:
        if start_on is not None or end_on is not None:
            raise DashboardValidationError("period", "Choisir une période ou deux dates, pas les deux.")
        if period == "day":
            return today, today
        if period == "week":
            first = today - timedelta(days=today.weekday())
            return first, first + timedelta(days=6)
        if period == "month":
            first = today.replace(day=1)
            next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
            return first, next_month - timedelta(days=1)
        raise DashboardValidationError("period", "La période est invalide.")
    if start_on is None or end_on is None:
        raise DashboardValidationError("start_on" if start_on is None else "end_on", "Deux dates sont requises.")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_on) is None:
        raise DashboardValidationError("start_on", "La date de début est invalide.")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_on) is None:
        raise DashboardValidationError("end_on", "La date de fin est invalide.")
    try:
        start = date.fromisoformat(start_on)
    except ValueError as error:
        raise DashboardValidationError("start_on", "La date de début est invalide.") from error
    try:
        end = date.fromisoformat(end_on)
    except ValueError as error:
        raise DashboardValidationError("end_on", "La date de fin est invalide.") from error
    if start > today:
        raise DashboardValidationError("start_on", "La date de début est future.")
    if end < start:
        raise DashboardValidationError("end_on", "La date de fin précède la date de début.")
    if (end - start).days + 1 > MAX_DAYS:
        raise DashboardValidationError("end_on", f"La plage ne peut pas dépasser {MAX_DAYS} jours.")
    return start, end


def _empty() -> dict[str, Any]:
    return {
        "prospects_by_stage": [{"stage_code": stage, "count": 0} for stage in STAGES],
        "tasks": {"due_today": 0, "overdue": 0},
        "activities_by_type": [{"type": kind, "count": 0} for kind in ACTIVITY_TYPES],
        "stage_passage": [],
        "stage_losses": [],
        "opportunities": {"open": 0, "won": 0, "lost": 0},
        "pipeline_by_currency": [],
    }


def _fold(rows: dict[str, list[dict[str, Any]]], owner: str | None, observed: str, complete: bool) -> dict[str, Any]:
    result = _empty()

    def selected(family: str) -> list[dict[str, Any]]:
        return [row for row in rows[family] if str(row["owner_membership_id"]) == owner]

    prospects = {item["stage_code"]: item for item in result["prospects_by_stage"]}
    for row in selected("prospects"):
        if row["stage_code"] in prospects:
            prospects[row["stage_code"]]["count"] = int(row["count"])
    for row in selected("tasks"):
        result["tasks"]["due_today"] += int(row["due_today"])
        result["tasks"]["overdue"] += int(row["overdue"])
    activities = {item["type"]: item for item in result["activities_by_type"]}
    for row in selected("activities"):
        if row["activity_type"] in activities:
            activities[row["activity_type"]]["count"] = int(row["count"])
    exits: dict[tuple[str, str | None], int] = {}
    for row in selected("stages"):
        key = (row["from_stage"], row["to_stage"])
        exits[key] = exits.get(key, 0) + int(row["count"])
    cohorts = {start: sum(count for (stage, _), count in exits.items() if stage == start) for start in LOSS_STAGES}
    result["stage_passage"] = [
        {
            "from_stage": start,
            "to_stage": end,
            "cohort": cohorts[start],
            "advanced": exits.get((start, end), 0),
            "rate_percent": f"{Decimal(exits.get((start, end), 0) * 100) / Decimal(cohorts[start]):.2f}"
            if cohorts[start]
            else None,
            "observed_until": observed,
            "window_complete": complete,
        }
        for start, end in PASSAGES
    ]
    result["stage_losses"] = [
        {"from_stage": start, "cohort": cohorts[start], "lost": exits.get((start, "lost"), 0)} for start in LOSS_STAGES
    ]
    currencies: dict[str, dict[str, Any]] = {}
    for row in selected("opportunities"):
        stage = row["stage_code"]
        count = int(row["count"])
        result["opportunities"]["open" if stage not in ("won", "lost") else stage] += count
        if stage in ("won", "lost"):
            continue
        code = row["currency_code"]
        entry = currencies.setdefault(
            code, {"currency_code": code, "amount": Decimal(0), "weighted_amount": Decimal(0)}
        )
        entry["amount"] += row["amount"]
        entry["weighted_amount"] += row["weighted_amount"]
    result["pipeline_by_currency"] = [
        {
            "currency_code": code,
            "amount": f"{value['amount']:.4f}",
            "weighted_amount": f"{value['weighted_amount']:.4f}",
        }
        for code, value in sorted(currencies.items())
    ]
    return result


class GetDashboardSummaryUseCase:
    def __init__(self, reader: DashboardReader, clock: Clock, usage: UsageStore | None = None) -> None:
        self._reader = reader
        self._clock = clock
        self._usage = usage

    async def execute(
        self,
        *,
        context: TenantContext,
        membership_id: UUID,
        timezone: str,
        scope: str,
        owner_membership_id: UUID | None,
        period: str | None,
        start_on: str | None,
        end_on: str | None,
        can_read_self: bool,
        can_read_organization: bool,
    ) -> dict[str, Any]:
        if scope not in ("self", "organization", "owner"):
            raise DashboardValidationError("scope", "La portée est invalide.")
        if (scope == "owner") != (owner_membership_id is not None):
            raise DashboardValidationError("owner_membership_id", "Le filtre responsable est invalide.")
        if (scope == "self" and not can_read_self) or (scope != "self" and not can_read_organization):
            raise PermissionError("Lecture du tableau de bord non autorisée.")
        now = self._clock.now().astimezone(UTC)
        zone = ZoneInfo(timezone)
        today = now.astimezone(zone).date()
        start, end = _period_dates(period, start_on, end_on, today)
        start_at = datetime.combine(start, time.min, zone).astimezone(UTC)
        end_at = datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(UTC)
        today_start = datetime.combine(today, time.min, zone).astimezone(UTC)
        today_end = datetime.combine(today + timedelta(days=1), time.min, zone).astimezone(UTC)
        target = membership_id if scope == "self" else owner_membership_id
        target_user = context.actor_id if scope == "self" else None
        if scope == "owner":
            assert target is not None
            target_user = await self._reader.owner_user_id(context, target)
            if target_user is None:
                raise DashboardOwnerNotFound
        query = DashboardQuery(
            context, scope, target, target_user, start_at, end_at, min(now, end_at), today_start, today_end, now
        )
        rows = await self._reader.read(query)
        google_usage: dict[str, Any] = {
            "status": "unavailable",
            "reason": "source_not_qualified",
            "used": None,
            "unit": None,
            "start_at_utc": None,
            "end_at_utc_exclusive": None,
            "timezone": None,
            "source": None,
        }
        if self._usage is not None:
            usage = await self._usage.report(context, start_on=start, end_on=end, user_id=target_user)
            used = sum(
                int(row["unit_count"])
                for row in usage["rows"]
                if row["usage_code"] == "google.places_text_search.quota" and row["outcome"] == "accepted"
            )
            google_usage = {
                "status": "available",
                "reason": None,
                "used": used,
                "unit": "reservation",
                "start_at_utc": _utc(start_at),
                "end_at_utc_exclusive": _utc(end_at),
                "timezone": "UTC",
                "source": "usage_quota_v1",
            }
        observed = _utc(query.observed_until)
        complete = end_at <= now
        if scope == "organization":
            owners = {str(row["owner_membership_id"]) for family in rows.values() for row in family}
            total = _fold(
                {family: [dict(row, owner_membership_id=None) for row in values] for family, values in rows.items()},
                "None",
                observed,
                complete,
            )
            breakdown = [
                dict(owner_membership_id=None if owner == "None" else owner, **_fold(rows, owner, observed, complete))
                for owner in sorted(owners)
            ]
        else:
            total = _fold(rows, str(target), observed, complete)
            breakdown = None
        return {
            "period": {
                "start_on": start.isoformat(),
                "end_on": end.isoformat(),
                "timezone": timezone,
                "start_at_utc": _utc(start_at),
                "end_at_utc_exclusive": _utc(end_at),
            },
            "as_of": _utc(now),
            "scope": {"kind": scope, "owner_membership_id": str(target) if target else None},
            "attribution": {
                "prospects_by_stage": "prospects.owner_id",
                "tasks": "prospect_tasks.assigned_membership_id",
                "activities_by_type": "prospect_activities.actor_id (initiale)",
                "stage_passage": "prospects.owner_id_current",
                "stage_losses": "prospects.owner_id_current",
                "opportunities": "opportunities.owner_membership_id",
                "pipeline_by_currency": "opportunities.owner_membership_id",
                "google_usage": "usage_daily_counters",
            },
            **total,
            "owner_breakdown": breakdown,
            "google_usage": google_usage,
        }
