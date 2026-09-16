from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .prospect import ProspectStageCode


class PipelineValidationError(ValueError):
    pass


class LostReasonCode(StrEnum):
    NO_NEED = "no_need"
    NO_BUDGET = "no_budget"
    NO_RESPONSE = "no_response"
    COMPETITOR = "competitor"
    TIMING = "timing"
    OUTSIDE_TERRITORY = "outside_territory"
    INVALID_OR_DUPLICATE = "invalid_or_duplicate"
    OTHER = "other"


class ReopenReasonCode(StrEnum):
    ENTERED_IN_ERROR = "entered_in_error"
    CUSTOMER_REENGAGED = "customer_reengaged"
    ADDITIONAL_INFORMATION = "additional_information"
    OTHER = "other"


PIPELINE_STAGES = (
    ProspectStageCode.NEW,
    ProspectStageCode.QUALIFYING,
    ProspectStageCode.QUALIFIED,
    ProspectStageCode.CONTACTED,
    ProspectStageCode.OPPORTUNITY,
    ProspectStageCode.PROPOSAL_SENT,
    ProspectStageCode.NEGOTIATION,
    ProspectStageCode.WON,
    ProspectStageCode.LOST,
)

DEFAULT_STAGE_LABELS: dict[ProspectStageCode, dict[str, str]] = {
    ProspectStageCode.NEW: {"fr-CA": "Nouveau", "en-CA": "New"},
    ProspectStageCode.QUALIFYING: {"fr-CA": "Qualification", "en-CA": "Qualifying"},
    ProspectStageCode.QUALIFIED: {"fr-CA": "Qualifié", "en-CA": "Qualified"},
    ProspectStageCode.CONTACTED: {"fr-CA": "Contacté", "en-CA": "Contacted"},
    ProspectStageCode.OPPORTUNITY: {"fr-CA": "Opportunité", "en-CA": "Opportunity"},
    ProspectStageCode.PROPOSAL_SENT: {"fr-CA": "Soumission envoyée", "en-CA": "Proposal sent"},
    ProspectStageCode.NEGOTIATION: {"fr-CA": "Négociation", "en-CA": "Negotiation"},
    ProspectStageCode.WON: {"fr-CA": "Gagné", "en-CA": "Won"},
    ProspectStageCode.LOST: {"fr-CA": "Perdu", "en-CA": "Lost"},
}

DEFAULT_STAGE_COLORS: dict[ProspectStageCode, str] = {
    ProspectStageCode.NEW: "slate",
    ProspectStageCode.QUALIFYING: "blue",
    ProspectStageCode.QUALIFIED: "indigo",
    ProspectStageCode.CONTACTED: "cyan",
    ProspectStageCode.OPPORTUNITY: "violet",
    ProspectStageCode.PROPOSAL_SENT: "amber",
    ProspectStageCode.NEGOTIATION: "orange",
    ProspectStageCode.WON: "green",
    ProspectStageCode.LOST: "red",
}

_TRANSITIONS: dict[ProspectStageCode, frozenset[ProspectStageCode]] = {
    ProspectStageCode.NEW: frozenset({ProspectStageCode.QUALIFYING, ProspectStageCode.LOST}),
    ProspectStageCode.QUALIFYING: frozenset(
        {ProspectStageCode.NEW, ProspectStageCode.QUALIFIED, ProspectStageCode.LOST}
    ),
    ProspectStageCode.QUALIFIED: frozenset(
        {ProspectStageCode.QUALIFYING, ProspectStageCode.CONTACTED, ProspectStageCode.LOST}
    ),
    ProspectStageCode.CONTACTED: frozenset(
        {ProspectStageCode.QUALIFIED, ProspectStageCode.OPPORTUNITY, ProspectStageCode.LOST}
    ),
    ProspectStageCode.OPPORTUNITY: frozenset(
        {ProspectStageCode.CONTACTED, ProspectStageCode.PROPOSAL_SENT, ProspectStageCode.LOST}
    ),
    ProspectStageCode.PROPOSAL_SENT: frozenset(
        {ProspectStageCode.OPPORTUNITY, ProspectStageCode.NEGOTIATION, ProspectStageCode.WON, ProspectStageCode.LOST}
    ),
    ProspectStageCode.NEGOTIATION: frozenset(
        {ProspectStageCode.PROPOSAL_SENT, ProspectStageCode.WON, ProspectStageCode.LOST}
    ),
    ProspectStageCode.WON: frozenset(),
    ProspectStageCode.LOST: frozenset(),
}


@dataclass(frozen=True, slots=True)
class PipelineStageView:
    code: ProspectStageCode
    position: int
    color_token: str
    labels: dict[str, str]
    version: int


@dataclass(frozen=True, slots=True)
class ProspectStageTransitionView:
    id: UUID
    prospect_id: UUID
    actor_id: UUID
    from_stage: ProspectStageCode
    to_stage: ProspectStageCode
    from_version: int
    resulting_version: int
    reason_code: str | None
    reason_note: str | None
    occurred_at: datetime


def ensure_transition_allowed(from_stage: ProspectStageCode, to_stage: ProspectStageCode) -> None:
    if from_stage is ProspectStageCode.ARCHIVED or to_stage is ProspectStageCode.ARCHIVED:
        raise PipelineValidationError("Une étape archivée ne peut pas être déplacée dans le pipeline.")
    if to_stage not in _TRANSITIONS.get(from_stage, frozenset()):
        raise PipelineValidationError("La transition demandée n’est pas permise.")


def validate_transition_reason(
    *, to_stage: ProspectStageCode, reason_code: str | None, reason_note: str | None
) -> tuple[str | None, str | None]:
    code = reason_code.strip() if reason_code else None
    note = reason_note.strip() if reason_note else None
    if note and len(note) > 500:
        raise PipelineValidationError("La note du motif ne peut pas dépasser 500 caractères.")
    if to_stage is ProspectStageCode.LOST:
        if code not in {item.value for item in LostReasonCode}:
            raise PipelineValidationError("Un motif de perte valide est obligatoire.")
        if code == LostReasonCode.OTHER.value and not note:
            raise PipelineValidationError("Une note est obligatoire pour le motif « autre ».")
    elif code is not None or note is not None:
        raise PipelineValidationError("Un motif n’est accepté que lors du passage à l’étape perdue.")
    return code, note


def validate_reopen_reason(reason_code: str, reason_note: str | None) -> tuple[str, str | None]:
    code = reason_code.strip()
    note = reason_note.strip() if reason_note else None
    if code not in {item.value for item in ReopenReasonCode}:
        raise PipelineValidationError("Le motif de réouverture est invalide.")
    if code == ReopenReasonCode.OTHER.value and not note:
        raise PipelineValidationError("Une note est obligatoire pour le motif « autre ».")
    if note and len(note) > 500:
        raise PipelineValidationError("La note du motif ne peut pas dépasser 500 caractères.")
    return code, note
