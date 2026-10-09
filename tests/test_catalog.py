from datetime import UTC, datetime, timedelta

import pytest

from backend.app.domain.catalog import (
    CatalogValidationError,
    EntitlementDecisionCode,
    EntitlementDecisionReason,
    EntitlementKey,
    EntitlementKind,
    EntitlementOverride,
    EntitlementProvenanceSource,
    EntitlementValue,
    OverrideState,
    resolve_effective_entitlement,
)

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)


def _limit(value: int) -> EntitlementValue:
    return EntitlementValue(EntitlementKey.ACTIVE_MEMBERS_MAX, EntitlementKind.LIMIT, integer_value=value)


def test_catalog_resolver_refuses_an_unknown_contract() -> None:
    result = resolve_effective_entitlement(
        key=EntitlementKey.ACTIVE_MEMBERS_MAX,
        contract_is_active=False,
        plan_value=_limit(5),
        override=None,
        now=NOW,
    )

    assert result.code is EntitlementDecisionCode.DENY_UNKNOWN_CONTRACT
    assert result.value is None
    assert result.allowed is False


def test_catalog_resolver_applies_a_valid_override_with_provenance() -> None:
    override = EntitlementOverride(
        value=_limit(7),
        state=OverrideState.ACTIVE,
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(hours=1),
    )

    result = resolve_effective_entitlement(
        key=EntitlementKey.ACTIVE_MEMBERS_MAX,
        contract_is_active=True,
        plan_value=_limit(5),
        override=override,
        now=NOW,
    )

    assert result.code is EntitlementDecisionCode.ALLOWED
    assert result.value == _limit(7)
    assert result.source == "override"
    assert tuple(item.source for item in result.provenance) == (
        EntitlementProvenanceSource.CONTRACT,
        EntitlementProvenanceSource.PLAN_VERSION,
        EntitlementProvenanceSource.OVERRIDE,
    )
    assert result.provenance[-1].applied is True


def test_catalog_resolver_never_allows_an_override_past_safety_ceiling() -> None:
    result = resolve_effective_entitlement(
        key=EntitlementKey.ACTIVE_MEMBERS_MAX,
        contract_is_active=True,
        plan_value=_limit(5),
        override=EntitlementOverride(
            value=_limit(7),
            state=OverrideState.ACTIVE,
            starts_at=NOW - timedelta(hours=1),
            ends_at=NOW + timedelta(hours=1),
        ),
        safety_ceiling=_limit(6),
        now=NOW,
    )

    assert result.code is EntitlementDecisionCode.SAFETY_CEILING_EXCEEDED
    assert result.allowed is False
    assert result.reason is EntitlementDecisionReason.SAFETY_CEILING_EXCEEDED
    assert result.provenance[-1].source is EntitlementProvenanceSource.SAFETY_CEILING


def test_catalog_resolver_keeps_the_stable_denial_code_and_records_the_contract_reason() -> None:
    result = resolve_effective_entitlement(
        key=EntitlementKey.ACTIVE_MEMBERS_MAX,
        contract_is_active=False,
        contract_reason=EntitlementDecisionReason.AMBIGUOUS_ACTIVE_CONTRACT,
        plan_value=_limit(5),
        override=None,
        now=NOW,
    )

    assert result.code is EntitlementDecisionCode.DENY_UNKNOWN_CONTRACT
    assert result.reason is EntitlementDecisionReason.AMBIGUOUS_ACTIVE_CONTRACT
    assert result.provenance == (result.provenance[0],)
    assert result.provenance[0].applied is False


def test_catalog_rejects_an_untyped_or_self_approved_override() -> None:
    with pytest.raises(CatalogValidationError):
        EntitlementValue(EntitlementKey.GOOGLE_PAID_CALLS_ENABLED, EntitlementKind.SWITCH, integer_value=1)
    with pytest.raises(CatalogValidationError):
        EntitlementOverride(
            value=_limit(7),
            state=OverrideState.ACTIVE,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=1),
            approved_by_is_creator=True,
        )
