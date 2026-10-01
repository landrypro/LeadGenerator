from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.domain.identity import CAPABILITIES_BY_ROLE, MembershipRole
from backend.app.domain.opportunity import (
    OpportunityDraft,
    OpportunityLossReasonCode,
    OpportunityStageCode,
    OpportunityValidationError,
    OpportunityView,
    validate_opportunity_draft,
    validate_opportunity_state,
)
from backend.app.infrastructure.postgres.models import Base

TODAY = date(2026, 9, 10)
NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


def _draft(**changes: object) -> OpportunityDraft:
    values: dict[str, object] = {
        "prospect_id": uuid4(),
        "owner_membership_id": uuid4(),
        "name": "  Soumission annuelle  ",
        "amount": Decimal("1250.2500"),
        "currency_code": "CAD",
        "probability": 25,
        "expected_close_on": TODAY + timedelta(days=1),
        "idempotency_key": str(uuid4()),
    }
    values.update(changes)
    return OpportunityDraft(**values)  # type: ignore[arg-type]


def test_opportunity_draft_normalizes_internal_fields_and_preserves_exact_decimal() -> None:
    draft = validate_opportunity_draft(_draft(), organization_today=TODAY)

    assert draft.name == "Soumission annuelle"
    assert draft.amount == Decimal("1250.2500")
    assert draft.currency_code == "CAD"

    view = OpportunityView(
        id=uuid4(),
        organization_id=uuid4(),
        prospect_id=draft.prospect_id,
        owner_membership_id=draft.owner_membership_id,
        name=draft.name,
        amount=draft.amount,
        currency_code=draft.currency_code,
        probability=25,
        stage_code=OpportunityStageCode.DISCOVERY,
        expected_close_on=draft.expected_close_on,
        loss_reason_code=None,
        loss_reason_note=None,
        closed_at=None,
        created_by=uuid4(),
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    assert view.weighted_amount == Decimal("312.5625")


@pytest.mark.parametrize(
    "amount",
    [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), Decimal("1.12345")],
)
def test_opportunity_draft_rejects_invalid_decimal_amounts(amount: Decimal) -> None:
    with pytest.raises(OpportunityValidationError, match="montant") as error:
        validate_opportunity_draft(_draft(amount=amount), organization_today=TODAY)
    assert error.value.field == "amount"


def test_opportunity_draft_rejects_float_invalid_currency_and_past_civil_date() -> None:
    with pytest.raises(OpportunityValidationError, match="décimal"):
        validate_opportunity_draft(_draft(amount=12.5), organization_today=TODAY)
    with pytest.raises(OpportunityValidationError, match="devise") as error:
        validate_opportunity_draft(_draft(currency_code="cad"), organization_today=TODAY)
    assert error.value.field == "currency_code"
    with pytest.raises(OpportunityValidationError, match="échéance") as error:
        validate_opportunity_draft(_draft(expected_close_on=TODAY - timedelta(days=1)), organization_today=TODAY)
    assert error.value.field == "expected_close_on"


def test_opportunity_draft_requires_bounded_text_probability_and_idempotency_key() -> None:
    with pytest.raises(OpportunityValidationError, match="nom"):
        validate_opportunity_draft(_draft(name=" "), organization_today=TODAY)
    with pytest.raises(OpportunityValidationError, match="probabilité"):
        validate_opportunity_draft(_draft(probability=101), organization_today=TODAY)
    with pytest.raises(OpportunityValidationError, match="idempotence"):
        validate_opportunity_draft(_draft(idempotency_key=""), organization_today=TODAY)


def test_opportunity_terminal_state_invariants_are_enforced() -> None:
    assert validate_opportunity_state(
        stage_code=OpportunityStageCode.DISCOVERY,
        probability=25,
        loss_reason_code=None,
        loss_reason_note=None,
        closed_at=None,
    ) == (25, None)
    assert validate_opportunity_state(
        stage_code=OpportunityStageCode.WON,
        probability=100,
        loss_reason_code=None,
        loss_reason_note=None,
        closed_at=NOW,
    ) == (100, None)
    assert validate_opportunity_state(
        stage_code=OpportunityStageCode.LOST,
        probability=0,
        loss_reason_code=OpportunityLossReasonCode.OTHER,
        loss_reason_note="  Périmètre non compatible  ",
        closed_at=NOW,
    ) == (0, "Périmètre non compatible")

    with pytest.raises(OpportunityValidationError, match="100"):
        validate_opportunity_state(
            stage_code=OpportunityStageCode.WON,
            probability=75,
            loss_reason_code=None,
            loss_reason_note=None,
            closed_at=NOW,
        )
    with pytest.raises(OpportunityValidationError, match="exige une note"):
        validate_opportunity_state(
            stage_code=OpportunityStageCode.LOST,
            probability=0,
            loss_reason_code=OpportunityLossReasonCode.OTHER,
            loss_reason_note=None,
            closed_at=NOW,
        )


def test_opportunity_capabilities_follow_the_validated_role_matrix() -> None:
    assert "opportunities:reopen" in CAPABILITIES_BY_ROLE[MembershipRole.ADMIN]
    assert "opportunities:reopen" in CAPABILITIES_BY_ROLE[MembershipRole.MANAGER]
    assert "opportunities:close" in CAPABILITIES_BY_ROLE[MembershipRole.SALES]
    assert "opportunities:reopen" not in CAPABILITIES_BY_ROLE[MembershipRole.SALES]


def test_opportunity_models_are_registered_in_schema_metadata() -> None:
    assert {"opportunities", "opportunity_events"} <= set(Base.metadata.tables)
