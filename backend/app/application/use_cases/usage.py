from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from ..models import GoogleAccessOwner
from ..ports.clock import Clock
from ..ports.google_quota import GoogleSearchPolicyProvider, GoogleSearchQuota
from ..ports.usage import UsageStore
from ..tenancy import TenantContext

MAX_REPORT_DAYS = 93
COLLECTION_STARTED_ON = date(2026, 9, 24)


class UsageValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class UsageOwnerNotFound(Exception):
    pass


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _dates(period: str, start_on: str | None, end_on: str | None, today: date) -> tuple[date, date]:
    if period != "custom":
        if start_on is not None or end_on is not None:
            raise UsageValidationError("period", "Choisir une période ou deux dates, pas les deux.")
        days = {"today": 1, "last_7_days": 7, "last_30_days": 30}.get(period)
        if days is None:
            raise UsageValidationError("period", "La période est invalide.")
        return today - timedelta(days=days - 1), today
    if start_on is None or end_on is None:
        raise UsageValidationError("start_on" if start_on is None else "end_on", "Deux dates sont requises.")
    for field, value in (("start_on", start_on), ("end_on", end_on)):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise UsageValidationError(field, "La date est invalide.")
    try:
        start, end = date.fromisoformat(start_on), date.fromisoformat(end_on)
    except ValueError as error:
        raise UsageValidationError("start_on", "La date est invalide.") from error
    if start > today or end < start or (end - start).days + 1 > MAX_REPORT_DAYS:
        raise UsageValidationError("end_on", "La plage doit être passée, ordonnée et limitée à 93 jours.")
    return start, end


def _empty_totals() -> dict[str, dict[str, int]]:
    return {
        "google.places_text_search.quota": {"accepted": 0, "rejected": 0},
        "google.places_text_search.request": {"attempted": 0, "succeeded": 0, "failed": 0, "indeterminate": 0},
        "google.places_autocomplete.request": {"attempted": 0, "succeeded": 0, "failed": 0, "indeterminate": 0},
        "google.places_details.request": {"attempted": 0, "succeeded": 0, "failed": 0, "indeterminate": 0},
        "google.maps_static.request": {"attempted": 0, "succeeded": 0, "failed": 0, "indeterminate": 0},
    }


class GetUsageReportUseCase:
    def __init__(self, store: UsageStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        membership_id: UUID,
        scope: str,
        owner_membership_id: UUID | None,
        period: str,
        start_on: str | None,
        end_on: str | None,
        group_by: str,
        can_read_self: bool,
        can_read_organization: bool,
    ) -> dict[str, Any]:
        if scope not in {"self", "organization", "owner"}:
            raise UsageValidationError("scope", "La portée est invalide.")
        if group_by != "day":
            raise UsageValidationError("group_by", "Le groupement est invalide.")
        if (scope == "owner") != (owner_membership_id is not None):
            raise UsageValidationError("owner_membership_id", "Le membre ciblé est invalide.")
        if (scope == "self" and not can_read_self) or (scope != "self" and not can_read_organization):
            raise PermissionError("Lecture de l’usage non autorisée.")
        now = self._clock.now().astimezone(UTC)
        start, end = _dates(period, start_on, end_on, now.date())
        target_membership = membership_id if scope == "self" else owner_membership_id
        target_user: UUID | None = context.actor_id if scope == "self" else None
        if scope == "owner":
            assert target_membership is not None
            target_user = await self._store.owner_user_id(context, target_membership)
            if target_user is None:
                raise UsageOwnerNotFound
        raw = await self._store.report(context, start_on=start, end_on=end, user_id=target_user)
        if scope != "self":
            await self._store.audit_report_view(context, scope=scope, start_on=start, end_on=end)
        return _format_report(raw, start, end, now, scope, target_membership)


class GetCurrentUsageUseCase:
    def __init__(
        self,
        store: UsageStore,
        quota: GoogleSearchQuota,
        policies: GoogleSearchPolicyProvider,
        clock: Clock,
    ) -> None:
        self._store = store
        self._quota = quota
        self._policies = policies
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        scope: str,
        can_read_self: bool,
        can_read_organization: bool,
    ) -> dict[str, Any]:
        if scope not in {"self", "organization"}:
            raise UsageValidationError("scope", "La portée est invalide.")
        if (scope == "self" and not can_read_self) or (scope == "organization" and not can_read_organization):
            raise PermissionError("Lecture de l’usage non autorisée.")
        owner = GoogleAccessOwner(context.actor_id, context.organization_id)
        policy = await self._policies.resolve(owner)
        now = self._clock.now().astimezone(UTC)
        reset_at = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
        durable = await self._store.report(
            context,
            start_on=now.date(),
            end_on=now.date(),
            user_id=context.actor_id if scope == "self" else None,
        )
        durable_used = sum(
            int(row["unit_count"])
            for row in durable["rows"]
            if row["usage_code"] == "google.places_text_search.quota" and row["outcome"] == "accepted"
        )
        source = "usage_daily_counters"
        enforcement = "unavailable"
        durable_org = await self._store.report(context, start_on=now.date(), end_on=now.date(), user_id=None)
        durable_org_used = sum(
            int(row["unit_count"])
            for row in durable_org["rows"]
            if row["usage_code"] == "google.places_text_search.quota" and row["outcome"] == "accepted"
        )
        user_used, organization_used = durable_used, durable_org_used
        try:
            current = await self._quota.current(owner, policy, now=now)
            user_used, organization_used = current.user_used, current.organization_used
            reset_at = current.reset_at
            source = "redis_quota"
            enforcement = "available"
        except Exception:
            pass
        used = user_used if scope == "self" else organization_used
        limit = policy.user_daily_limit if scope == "self" else policy.organization_daily_limit

        def quota_values(value: int, quota_limit: int) -> dict[str, int]:
            return {"used": value, "remaining": max(quota_limit - value, 0), "limit": quota_limit}

        return {
            "scope": scope,
            "used": used,
            "remaining": max(limit - used, 0),
            "limit": limit,
            "warning_threshold_percent": policy.warning_threshold_percent,
            "reset_at": _utc(reset_at),
            "timezone": "UTC",
            "unit": "reservation",
            "policy_code": policy.policy_code,
            "source": source,
            "enforcement_status": enforcement,
            "user": quota_values(user_used, policy.user_daily_limit),
            "organization": quota_values(organization_used, policy.organization_daily_limit),
        }


def _format_report(
    raw: dict[str, Any], start: date, end: date, now: datetime, scope: str, membership_id: UUID | None
) -> dict[str, Any]:
    totals = _empty_totals()
    series: dict[str, dict[str, Any]] = {}
    exports = {"requested": 0, "ready": 0, "failed": 0, "expired": 0, "rows": 0, "omitted": 0, "bytes": 0}
    imports = {"confirmed_runs": 0, "examined_rows": 0, "created": 0, "duplicates": 0, "review": 0, "quarantined": 0}
    for row in raw["rows"]:
        code, kind, outcome, count = row["usage_code"], row["event_kind"], row["outcome"], int(row["unit_count"])
        day = row["usage_day"].isoformat()
        bucket = series.setdefault(day, {"date": day, "operations": {}})
        bucket["operations"][f"{code}:{kind}:{outcome}"] = count
        if code in totals:
            key = outcome if kind != "upstream_attempted" else "attempted"
            if key in totals[code]:
                totals[code][key] += count
        elif code == "platform.csv_export":
            key = {
                "export_requested": "requested",
                "export_ready": "ready",
                "export_failed": "failed",
                "export_expired": "expired",
            }.get(kind)
            if key:
                exports[key] += count
            exports["rows"] += int(row["row_count"] or 0)
            exports["omitted"] += int(row["omitted_count"] or 0)
            exports["bytes"] += int(row["byte_count"] or 0)
        elif code == "platform.csv_import":
            imports["confirmed_runs"] += count
            imports["examined_rows"] += int(row["row_count"] or 0)
            imports["created"] += int(row["created_count"] or 0)
            imports["duplicates"] += int(row["duplicate_count"] or 0)
            imports["review"] += int(row["review_count"] or 0)
            imports["quarantined"] += int(row["quarantined_count"] or 0)
    start_at = datetime.combine(start, time.min, tzinfo=UTC)
    end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
    owners: dict[str, dict[str, Any]] = {}
    for row in raw.get("owner_rows", []):
        membership = str(row["owner_membership_id"])
        entry = owners.setdefault(membership, {"owner_membership_id": membership, "operations": {}})
        key = f"{row['usage_code']}:{row['event_kind']}:{row['outcome']}"
        entry["operations"][key] = int(row["unit_count"])
    is_partial = start < COLLECTION_STARTED_ON
    return {
        "period": {
            "start_on": start.isoformat(),
            "end_on": end.isoformat(),
            "timezone": "UTC",
            "start_at_utc": _utc(start_at),
            "end_at_utc_exclusive": _utc(end_at),
        },
        "as_of": _utc(now),
        "scope": {"kind": scope, "owner_membership_id": str(membership_id) if scope == "owner" else None},
        "completeness": {
            "status": "partial" if is_partial else "complete",
            "reason": "legacy_period" if is_partial else None,
            "last_recorded_at": _utc(raw["last_recorded_at"]) if raw["last_recorded_at"] else None,
        },
        "google": {
            "billing": {"status": "unavailable", "reason": "billing_source_not_integrated", "amount": None},
            "totals": [
                dict(code=code, unit="reservation" if code.endswith(".quota") else "upstream_request", **values)
                for code, values in totals.items()
            ],
        },
        "platform": {"csv_export": exports, "csv_import": imports},
        "series": [series[key] for key in sorted(series)],
        "owner_breakdown": [owners[key] for key in sorted(owners)] if scope == "organization" else None,
    }
