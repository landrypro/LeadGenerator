from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.application.audit_events import tenant_audit_event
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.export_contract import (
    DATASETS,
    build_query,
    canonical_columns,
    csv_row,
    validate_filters,
)
from backend.app.domain.audit import AuditAction
from backend.app.infrastructure.postgres.export_service import ExportService


def test_csv_contract_neutralizes_formulas_and_keeps_rfc4180_quoting() -> None:
    values = {"title": " \t=2+2", "summary": 'bonjour, "équipe"\nmerci', "amount": "42.5000"}
    rendered = csv_row(("title", "summary", "amount"), values)
    assert next(csv.reader(io.StringIO(rendered.decode("utf-8")))) == [
        "'  =2+2",
        'bonjour, "équipe" merci',
        "42.5000",
    ]
    assert rendered.endswith(b"\r\n")


def test_closed_columns_and_dst_date_bounds() -> None:
    dataset = DATASETS["prospects"]
    assert canonical_columns(dataset, ["created_at", "prospect_id"]) == ("prospect_id", "created_at")
    with pytest.raises(ValueError, match="invalid_column"):
        canonical_columns(dataset, ["google_place_id"])
    filters = validate_filters(
        dataset, {"created_from": "2026-03-08", "created_to": "2026-03-08"}, timezone_name="America/Toronto"
    )
    _, params = build_query(dataset, scope="self", filters=filters, timezone_name="America/Toronto")
    assert params["created_from"] == datetime(2026, 3, 8, 5, tzinfo=UTC)
    assert params["created_to"] == datetime(2026, 3, 9, 4, tzinfo=UTC)


def test_export_source_rules_do_not_match_other_acquisition_with_null_provider() -> None:
    now = datetime(2026, 9, 24, tzinfo=UTC)
    acquisition = uuid4()
    row = {
        "_source_kind": "csv",
        "_source_purpose": "commercial_follow_up",
        "_acquisition_id": acquisition,
        "_provider_id": None,
        "_acquisition_status": "approved",
        "_provider_status": None,
    }
    rule = {
        "data_category": "person_identity",
        "purpose": "commercial_follow_up",
        "acquisition_id": uuid4(),
        "provider_id": None,
        "valid_from": now,
        "valid_until": None,
        "field_codes": ["display_name"],
        "status": "allowed",
    }
    assert ExportService._allowed_fields(row, "person_identity", [rule], now) == set()
    rule["acquisition_id"] = acquisition
    assert ExportService._allowed_fields(row, "person_identity", [rule], now) == {"display_name"}
    rule["status"] = "unknown"
    assert ExportService._allowed_fields(row, "person_identity", [rule], now) == set()
    row["_source_kind"] = "google_maps"
    rule["status"] = "allowed"
    assert ExportService._allowed_fields(row, "person_identity", [rule], now) == set()


def test_google_origin_alias_stays_excluded_after_manual_profile_update() -> None:
    row = {"_source_kind": "manual", "_prospect_origin": "google_place"}
    allowed = ExportService._allowed_fields(row, "prospect_profile", [], datetime(2026, 9, 24, tzinfo=UTC))
    assert "internal_alias" not in allowed
    assert "city" not in allowed
    row["_prospect_origin"] = "import"
    assert ExportService._allowed_fields(row, "prospect_profile", [], datetime(2026, 9, 24, tzinfo=UTC)) == set()


def test_export_audit_metadata_is_closed_and_minimized() -> None:
    context = TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="test-export")
    event = tenant_audit_event(
        context,
        AuditAction.EXPORT_REQUESTED,
        uuid4(),
        {
            "dataset": "prospects",
            "scope": "self",
            "filters": {"created_from": "2026-09-24"},
            "column_count": 7,
        },
    )
    assert event.entity_type == "export_request"
    with pytest.raises(ValueError):
        tenant_audit_event(
            context,
            AuditAction.EXPORT_REQUESTED,
            uuid4(),
            {
                "dataset": "prospects",
                "scope": "self",
                "filters": {"search": "a person"},
                "column_count": 7,
            },
        )
