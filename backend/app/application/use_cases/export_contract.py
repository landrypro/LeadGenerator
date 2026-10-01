"""Closed, versioned CSV contract for internal CRM exports."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

MAX_EXPORT_ROWS = 50_000
MAX_EXPORT_BYTES = 50 * 1024 * 1024
MAX_ACTIVE_EXPORTS = 5
MAX_ORG_ARTIFACT_BYTES = 250 * 1024 * 1024
EXPORT_TTL = timedelta(hours=24)
SCHEMA_CODE = "crm_csv_v1"
_FORMULA_PREFIX = re.compile(r"^[\s\x00-\x1f\x7f]*[=+\-@]")
_PROFILE_FIELDS = frozenset(
    {
        "internal_alias",
        "industry_label",
        "segment_code",
        "size_band",
        "address_line_1",
        "address_line_2",
        "city",
        "region",
        "postal_code",
        "country_code",
    }
)


@dataclass(frozen=True, slots=True)
class Dataset:
    code: str
    from_sql: str
    columns: tuple[str, ...]
    defaults: tuple[str, ...]
    read_capability: str
    self_sql: str
    date_column: str
    owner_column: str | None = None
    stage_column: str | None = None
    status_column: str | None = None
    priority_column: str | None = None
    source_category: str | None = None


_PROSPECT_SOURCE = """
    LEFT JOIN provenance_records pr ON pr.id = p.profile_provenance_id
    LEFT JOIN acquisition_records acq ON acq.id = pr.acquisition_record_id
    LEFT JOIN source_providers sp ON sp.id = pr.provider_id
"""
_CONTACT_SOURCE = """
    JOIN provenance_records pr ON pr.id = c.provenance_id
    LEFT JOIN acquisition_records acq ON acq.id = pr.acquisition_record_id
    LEFT JOIN source_providers sp ON sp.id = pr.provider_id
"""
_CHANNEL_SOURCE = """
    JOIN provenance_records pr ON pr.id = ch.provenance_id
    LEFT JOIN acquisition_records acq ON acq.id = pr.acquisition_record_id
    LEFT JOIN source_providers sp ON sp.id = pr.provider_id
"""
SOURCE_COLUMNS = """
    pr.source_kind AS _source_kind, pr.purpose AS _source_purpose,
    pr.acquisition_record_id AS _acquisition_id, pr.provider_id AS _provider_id,
    acq.status AS _acquisition_status, sp.status AS _provider_status,
    sp.valid_from AS _provider_from, sp.valid_until AS _provider_until
"""

DATASETS: dict[str, Dataset] = {
    "prospects": Dataset(
        "prospects",
        "prospects p " + _PROSPECT_SOURCE,
        (
            "prospect_id",
            "internal_alias",
            "stage_code",
            "owner_membership_id",
            "priority",
            "tags",
            "industry_label",
            "segment_code",
            "size_band",
            "address_line_1",
            "address_line_2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "created_at",
            "updated_at",
        ),
        ("prospect_id", "internal_alias", "stage_code", "owner_membership_id", "priority", "tags", "created_at"),
        "prospects:read",
        "p.owner_id = :membership_id",
        "p.created_at",
        "p.owner_id",
        "p.stage_code",
        priority_column="p.priority",
        source_category="prospect_profile",
    ),
    "contacts": Dataset(
        "contacts",
        "contacts c JOIN prospects p ON p.id = c.prospect_id " + _CONTACT_SOURCE,
        ("contact_id", "prospect_id", "display_name", "role_label", "created_at"),
        ("contact_id", "prospect_id", "display_name", "created_at"),
        "contacts:read",
        "p.owner_id = :membership_id",
        "c.created_at",
        "p.owner_id",
        source_category="person_identity",
    ),
    "contact_channels": Dataset(
        "contact_channels",
        "contact_channels ch LEFT JOIN contacts c ON c.id = ch.contact_id "
        "JOIN prospects p ON p.id = COALESCE(ch.prospect_id, c.prospect_id) " + _CHANNEL_SOURCE,
        (
            "channel_id",
            "prospect_id",
            "contact_id",
            "channel_type",
            "value",
            "purpose",
            "permission_status",
            "obtained_at",
        ),
        ("channel_id", "prospect_id", "contact_id", "channel_type", "value", "purpose"),
        "contacts:read",
        "p.owner_id = :membership_id",
        "ch.obtained_at",
        "p.owner_id",
        source_category="channel",
    ),
    "activities": Dataset(
        "activities",
        "prospect_activities a JOIN prospects p ON p.id = a.prospect_id",
        (
            "activity_id",
            "prospect_id",
            "contact_id",
            "activity_type",
            "direction",
            "summary",
            "occurred_at",
            "actor_user_id",
        ),
        ("activity_id", "prospect_id", "activity_type", "direction", "summary", "occurred_at"),
        "activities:read",
        "a.actor_id = :actor_id",
        "a.occurred_at",
    ),
    "tasks": Dataset(
        "tasks",
        "prospect_tasks t JOIN prospects p ON p.id = t.prospect_id",
        ("task_id", "prospect_id", "assigned_membership_id", "title", "priority", "status", "due_at", "completed_at"),
        ("task_id", "prospect_id", "assigned_membership_id", "title", "priority", "status", "due_at"),
        "tasks:read",
        "t.assigned_membership_id = :membership_id",
        "t.due_at",
        "t.assigned_membership_id",
        status_column="t.status",
        priority_column="t.priority",
    ),
    "opportunities": Dataset(
        "opportunities",
        "opportunities o JOIN prospects p ON p.id = o.prospect_id",
        (
            "opportunity_id",
            "prospect_id",
            "owner_membership_id",
            "name",
            "amount",
            "currency_code",
            "probability",
            "stage_code",
            "expected_close_on",
            "closed_at",
        ),
        (
            "opportunity_id",
            "prospect_id",
            "owner_membership_id",
            "name",
            "amount",
            "currency_code",
            "probability",
            "stage_code",
            "expected_close_on",
        ),
        "opportunities:read",
        "o.owner_membership_id = :membership_id",
        "o.expected_close_on",
        "o.owner_membership_id",
        stage_column="o.stage_code",
    ),
}

_PROJECTIONS: dict[str, dict[str, str]] = {
    "prospects": {
        "prospect_id": "p.id",
        "internal_alias": "p.internal_alias",
        "stage_code": "p.stage_code",
        "owner_membership_id": "p.owner_id",
        "priority": "p.priority",
        "tags": "p.tags",
        "industry_label": "p.industry_label",
        "segment_code": "p.segment_code",
        "size_band": "p.size_band",
        "address_line_1": "p.address_line_1",
        "address_line_2": "p.address_line_2",
        "city": "p.city",
        "region": "p.region",
        "postal_code": "p.postal_code",
        "country_code": "p.country_code",
        "created_at": "p.created_at",
        "updated_at": "p.updated_at",
    },
    "contacts": {
        "contact_id": "c.id",
        "prospect_id": "c.prospect_id",
        "display_name": "c.display_name",
        "role_label": "c.role_label",
        "created_at": "c.created_at",
    },
    "contact_channels": {
        "channel_id": "ch.id",
        "prospect_id": "ch.prospect_id",
        "contact_id": "ch.contact_id",
        "channel_type": "ch.channel_type",
        "value": "ch.value",
        "purpose": "ch.purpose",
        "permission_status": "COALESCE((SELECT cp.status FROM contact_permissions cp WHERE cp.channel_id = ch.id AND (cp.valid_from IS NULL OR cp.valid_from <= :snapshot_at) AND (cp.valid_until IS NULL OR cp.valid_until > :snapshot_at) ORDER BY cp.updated_at DESC, cp.id DESC LIMIT 1), 'unknown')",
        "obtained_at": "ch.obtained_at",
    },
    "activities": {
        "activity_id": "a.id",
        "prospect_id": "a.prospect_id",
        "contact_id": "a.contact_id",
        "activity_type": "a.activity_type",
        "direction": "a.direction",
        "summary": "a.summary",
        "occurred_at": "a.occurred_at",
        "actor_user_id": "a.actor_id",
    },
    "tasks": {
        "task_id": "t.id",
        "prospect_id": "t.prospect_id",
        "assigned_membership_id": "t.assigned_membership_id",
        "title": "t.title",
        "priority": "t.priority",
        "status": "t.status",
        "due_at": "t.due_at",
        "completed_at": "t.completed_at",
    },
    "opportunities": {
        "opportunity_id": "o.id",
        "prospect_id": "o.prospect_id",
        "owner_membership_id": "o.owner_membership_id",
        "name": "o.name",
        "amount": "o.amount",
        "currency_code": "o.currency_code",
        "probability": "o.probability",
        "stage_code": "o.stage_code",
        "expected_close_on": "o.expected_close_on",
        "closed_at": "o.closed_at",
    },
}


def canonical_columns(dataset: Dataset, requested: list[str] | None) -> tuple[str, ...]:
    if requested is None:
        return dataset.defaults
    if (
        not requested
        or len(set(requested)) != len(requested)
        or any(column not in dataset.columns for column in requested)
    ):
        raise ValueError("invalid_column")
    return tuple(column for column in dataset.columns if column in requested)


def validate_filters(dataset: Dataset, filters: dict[str, Any], *, timezone_name: str) -> dict[str, Any]:
    date_prefix = {
        "prospects": "created",
        "contacts": "created",
        "contact_channels": "obtained",
        "activities": "occurred",
        "tasks": "due",
        "opportunities": "expected_close",
    }[dataset.code]
    allowed = {f"{date_prefix}_from", f"{date_prefix}_to"}
    if dataset.stage_column:
        allowed.add("stage_code")
    if dataset.status_column:
        allowed.add("status")
    if dataset.priority_column:
        allowed.add("priority")
    if dataset.owner_column:
        allowed.add("owner_membership_id")
    if set(filters) - allowed:
        raise ValueError("invalid_filter")
    result: dict[str, Any] = {}
    start = end = None
    for key in (f"{date_prefix}_from", f"{date_prefix}_to"):
        if key in filters:
            try:
                date_value = date.fromisoformat(str(filters[key]))
            except ValueError as error:
                raise ValueError("invalid_filter") from error
            result[key] = date_value.isoformat()
            if key.endswith("_from"):
                start = date_value
            else:
                end = date_value
    if start and end and (end < start or (end - start).days > 366):
        raise ValueError("invalid_filter")
    for key in allowed - {f"{date_prefix}_from", f"{date_prefix}_to"}:
        if key in filters:
            text_value = str(filters[key]).strip()
            if not text_value or len(text_value) > 64 or not re.fullmatch(r"[a-zA-Z0-9_-]+", text_value):
                raise ValueError("invalid_filter")
            result[key] = text_value
    if "owner_membership_id" in result:
        try:
            result["owner_membership_id"] = str(UUID(result["owner_membership_id"]))
        except ValueError as error:
            raise ValueError("invalid_filter") from error
    ZoneInfo(timezone_name)
    return dict(sorted(result.items()))


def build_query(
    dataset: Dataset, *, scope: str, filters: dict[str, Any], timezone_name: str
) -> tuple[str, dict[str, Any]]:
    projection = _PROJECTIONS[dataset.code]
    selected = [f"{expression} AS {name}" for name, expression in projection.items()]
    if dataset.source_category:
        selected.append(SOURCE_COLUMNS)
    if dataset.code == "prospects":
        selected.append("p.origin AS _prospect_origin")
    where = ["p.archived_at IS NULL"]
    params: dict[str, Any] = {}
    if dataset.code == "contacts":
        where.append("c.archived_at IS NULL")
    elif dataset.code == "contact_channels":
        where.extend(["ch.archived_at IS NULL", "(c.id IS NULL OR c.archived_at IS NULL)"])
    if scope == "self":
        where.append(dataset.self_sql)
    date_prefix = {
        "prospects": "created",
        "contacts": "created",
        "contact_channels": "obtained",
        "activities": "occurred",
        "tasks": "due",
        "opportunities": "expected_close",
    }[dataset.code]
    zone = ZoneInfo(timezone_name)
    for suffix in ("from", "to"):
        key = f"{date_prefix}_{suffix}"
        if key not in filters:
            continue
        value = date.fromisoformat(filters[key])
        if dataset.code == "opportunities":
            params[key] = value if suffix == "from" else value + timedelta(days=1)
        else:
            bound = value if suffix == "from" else value + timedelta(days=1)
            params[key] = datetime.combine(bound, time.min, tzinfo=zone).astimezone(UTC)
        where.append(f"{dataset.date_column} {'>=' if suffix == 'from' else '<'} :{key}")
    for key, column in (
        ("stage_code", dataset.stage_column),
        ("status", dataset.status_column),
        ("priority", dataset.priority_column),
        ("owner_membership_id", dataset.owner_column),
    ):
        if key in filters and column:
            where.append(f"{column} = :{key}")
            params[key] = filters[key]
    id_column = next(iter(projection.values()))
    sql = f"SELECT {', '.join(selected)} FROM {dataset.from_sql} WHERE {' AND '.join(where)} ORDER BY {id_column}"
    return sql, params


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    elif isinstance(value, date):
        value = value.isoformat()
    elif isinstance(value, Decimal):
        value = f"{value:.4f}"
    elif isinstance(value, (list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        value = str(value)
    normalized = str(value).replace("\x00", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return "'" + normalized if _FORMULA_PREFIX.match(normalized) else normalized


def csv_row(columns: tuple[str, ...], values: dict[str, Any]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([format_cell(values.get(column)) for column in columns])
    return buffer.getvalue().encode("utf-8")


def profile_columns() -> frozenset[str]:
    return _PROFILE_FIELDS
