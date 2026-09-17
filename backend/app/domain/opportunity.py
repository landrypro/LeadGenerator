from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final
from uuid import UUID


class OpportunityValidationError(ValueError):
    """Une opportunité ne respecte pas son contrat métier."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class OpportunityStageCode(StrEnum):
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class OpportunityEventType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    STAGE_CHANGED = "stage_changed"
    REOPENED = "reopened"


class OpportunityLossReasonCode(StrEnum):
    NO_NEED = "no_need"
    NO_BUDGET = "no_budget"
    NO_RESPONSE = "no_response"
    COMPETITOR = "competitor"
    TIMING = "timing"
    SCOPE_MISMATCH = "scope_mismatch"
    INVALID_OR_DUPLICATE = "invalid_or_duplicate"
    OTHER = "other"


class OpportunityReopenReasonCode(StrEnum):
    ENTERED_IN_ERROR = "entered_in_error"
    CUSTOMER_REENGAGED = "customer_reengaged"
    ADDITIONAL_INFORMATION = "additional_information"
    OTHER = "other"


OPEN_OPPORTUNITY_STAGES: Final = frozenset(
    {
        OpportunityStageCode.DISCOVERY,
        OpportunityStageCode.QUALIFICATION,
        OpportunityStageCode.PROPOSAL,
        OpportunityStageCode.NEGOTIATION,
    }
)
TERMINAL_OPPORTUNITY_STAGES: Final = frozenset({OpportunityStageCode.WON, OpportunityStageCode.LOST})

# ISO 4217 active codes supported by the CRM. This server-owned set is deliberately
# independent from browser data and is only used for validation, never conversion.
ISO_4217_CURRENCY_CODES: Final = frozenset(
    {
        "AED",
        "AFN",
        "ALL",
        "AMD",
        "ANG",
        "AOA",
        "ARS",
        "AUD",
        "AWG",
        "AZN",
        "BAM",
        "BBD",
        "BDT",
        "BGN",
        "BHD",
        "BIF",
        "BMD",
        "BND",
        "BOB",
        "BOV",
        "BRL",
        "BSD",
        "BTN",
        "BWP",
        "BYN",
        "BZD",
        "CAD",
        "CDF",
        "CHE",
        "CHF",
        "CHW",
        "CLF",
        "CLP",
        "CNY",
        "COP",
        "COU",
        "CRC",
        "CUP",
        "CVE",
        "CZK",
        "DJF",
        "DKK",
        "DOP",
        "DZD",
        "EGP",
        "ERN",
        "ETB",
        "EUR",
        "FJD",
        "FKP",
        "GBP",
        "GEL",
        "GHS",
        "GIP",
        "GMD",
        "GNF",
        "GTQ",
        "GYD",
        "HKD",
        "HNL",
        "HTG",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "IQD",
        "IRR",
        "ISK",
        "JMD",
        "JOD",
        "JPY",
        "KES",
        "KGS",
        "KHR",
        "KMF",
        "KPW",
        "KRW",
        "KWD",
        "KYD",
        "KZT",
        "LAK",
        "LBP",
        "LKR",
        "LRD",
        "LSL",
        "LYD",
        "MAD",
        "MDL",
        "MGA",
        "MKD",
        "MMK",
        "MNT",
        "MOP",
        "MRU",
        "MUR",
        "MVR",
        "MWK",
        "MXN",
        "MXV",
        "MYR",
        "MZN",
        "NAD",
        "NGN",
        "NIO",
        "NOK",
        "NPR",
        "NZD",
        "OMR",
        "PAB",
        "PEN",
        "PGK",
        "PHP",
        "PKR",
        "PLN",
        "PYG",
        "QAR",
        "RON",
        "RSD",
        "RUB",
        "RWF",
        "SAR",
        "SBD",
        "SCR",
        "SDG",
        "SEK",
        "SGD",
        "SHP",
        "SLE",
        "SLL",
        "SOS",
        "SRD",
        "SSP",
        "STN",
        "SVC",
        "SYP",
        "SZL",
        "THB",
        "TJS",
        "TMT",
        "TND",
        "TOP",
        "TRY",
        "TTD",
        "TWD",
        "TZS",
        "UAH",
        "UGX",
        "USD",
        "USN",
        "UYI",
        "UYU",
        "UYW",
        "UZS",
        "VED",
        "VES",
        "VND",
        "VUV",
        "WST",
        "XAF",
        "XCD",
        "XDR",
        "XOF",
        "XPF",
        "XSU",
        "XUA",
        "YER",
        "ZAR",
        "ZMW",
        "ZWL",
    }
)

_MAX_AMOUNT: Final = Decimal("999999999999999.9999")
_MIN_AMOUNT: Final = Decimal("0.0001")
_MONEY_QUANTUM: Final = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class OpportunityDraft:
    prospect_id: UUID
    owner_membership_id: UUID
    name: str
    amount: Decimal
    currency_code: str
    probability: int
    expected_close_on: date
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class OpportunityView:
    id: UUID
    organization_id: UUID
    prospect_id: UUID
    owner_membership_id: UUID
    name: str
    amount: Decimal
    currency_code: str
    probability: int
    stage_code: OpportunityStageCode
    expected_close_on: date
    loss_reason_code: OpportunityLossReasonCode | None
    loss_reason_note: str | None
    closed_at: datetime | None
    created_by: UUID
    version: int
    created_at: datetime
    updated_at: datetime
    owner_membership_is_active: bool = True

    @property
    def weighted_amount(self) -> Decimal:
        return (self.amount * Decimal(self.probability) / Decimal("100")).quantize(_MONEY_QUANTUM)


@dataclass(frozen=True, slots=True)
class OpportunityEventView:
    id: UUID
    organization_id: UUID
    prospect_id: UUID
    opportunity_id: UUID
    actor_id: UUID
    event_type: OpportunityEventType
    from_stage: OpportunityStageCode | None
    to_stage: OpportunityStageCode | None
    from_version: int
    resulting_version: int
    changed_fields: dict[str, str]
    reason_code: str | None
    reason_note: str | None
    idempotency_key: str
    command_fingerprint: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class OpportunityCurrencyAggregate:
    currency_code: str
    count: int
    amount_total: Decimal
    weighted_amount_total: Decimal
    open_count: int
    won_count: int
    lost_count: int
    overdue_open_count: int


@dataclass(frozen=True, slots=True)
class OpportunityProspectSummary:
    prospect_id: UUID
    open_count: int
    has_won_opportunity: bool
    next_expected_close_on: date | None
    overdue_open_count: int
    aggregates_by_currency: tuple[OpportunityCurrencyAggregate, ...]


def validate_opportunity_draft(draft: OpportunityDraft, *, organization_today: date) -> OpportunityDraft:
    name = _required_text(draft.name, field="Le nom de l’opportunité", maximum=160, error_field="name")
    amount = _validated_amount(draft.amount)
    currency_code = _validated_currency(draft.currency_code)
    probability = _validated_probability(draft.probability)
    if isinstance(draft.expected_close_on, datetime) or not isinstance(draft.expected_close_on, date):
        raise OpportunityValidationError("L’échéance doit être une date civile.", field="expected_close_on")
    if draft.expected_close_on < organization_today:
        raise OpportunityValidationError(
            "L’échéance ne peut pas précéder le jour courant de l’organisation.", field="expected_close_on"
        )
    return OpportunityDraft(
        prospect_id=draft.prospect_id,
        owner_membership_id=draft.owner_membership_id,
        name=name,
        amount=amount,
        currency_code=currency_code,
        probability=probability,
        expected_close_on=draft.expected_close_on,
        idempotency_key=_required_text(
            draft.idempotency_key, field="La clé d’idempotence", maximum=128, error_field="idempotency_key"
        ),
    )


def validate_opportunity_state(
    *,
    stage_code: OpportunityStageCode,
    probability: int,
    loss_reason_code: OpportunityLossReasonCode | None,
    loss_reason_note: str | None,
    closed_at: datetime | None,
) -> tuple[int, str | None]:
    probability = _validated_probability(probability)
    note = _optional_text(loss_reason_note, field="La note de perte", maximum=500)
    if stage_code in OPEN_OPPORTUNITY_STAGES:
        if loss_reason_code is not None or note is not None or closed_at is not None:
            raise OpportunityValidationError("Une opportunité ouverte ne peut pas porter d’issue.")
        return probability, None
    if closed_at is None or closed_at.tzinfo is None:
        raise OpportunityValidationError("Une opportunité terminale doit être clôturée avec un horodatage UTC.")
    if stage_code is OpportunityStageCode.WON:
        if probability != 100 or loss_reason_code is not None or note is not None:
            raise OpportunityValidationError(
                "Une opportunité gagnée doit porter une probabilité de 100 sans motif de perte."
            )
        return probability, None
    if stage_code is OpportunityStageCode.LOST:
        if probability != 0 or loss_reason_code is None:
            raise OpportunityValidationError("Une opportunité perdue doit porter une probabilité de 0 et un motif.")
        if loss_reason_code is OpportunityLossReasonCode.OTHER and note is None:
            raise OpportunityValidationError("Le motif « autre » exige une note.")
        return probability, note
    raise OpportunityValidationError("L’étape de l’opportunité est invalide.")


def _validated_amount(value: Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise OpportunityValidationError("Le montant doit être un décimal exact.", field="amount")
    if not value.is_finite() or value < _MIN_AMOUNT or value > _MAX_AMOUNT:
        raise OpportunityValidationError("Le montant est hors limites.", field="amount")
    try:
        if value.quantize(_MONEY_QUANTUM) != value:
            raise OpportunityValidationError(
                "Le montant ne peut pas contenir plus de quatre décimales.", field="amount"
            )
    except InvalidOperation as error:
        raise OpportunityValidationError("Le montant est invalide.", field="amount") from error
    return value


def _validated_currency(value: str) -> str:
    if not isinstance(value, str) or value not in ISO_4217_CURRENCY_CODES:
        raise OpportunityValidationError("La devise est invalide.", field="currency_code")
    return value


def _validated_probability(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise OpportunityValidationError(
            "La probabilité doit être un entier compris entre 0 et 100.", field="probability"
        )
    return value


def _required_text(value: str, *, field: str, maximum: int, error_field: str | None = None) -> str:
    if not isinstance(value, str):
        raise OpportunityValidationError(f"{field} est invalide.", field=error_field)
    result = value.strip()
    if not result or len(result) > maximum:
        raise OpportunityValidationError(f"{field} est invalide.", field=error_field)
    return result


def _optional_text(value: str | None, *, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _required_text(value, field=field, maximum=maximum)
