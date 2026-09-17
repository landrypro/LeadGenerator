from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID, uuid4

from ...domain.audit import AuditAction
from ...domain.opportunity import (
    OPEN_OPPORTUNITY_STAGES,
    OpportunityCurrencyAggregate,
    OpportunityDraft,
    OpportunityEventType,
    OpportunityEventView,
    OpportunityLossReasonCode,
    OpportunityProspectSummary,
    OpportunityReopenReasonCode,
    OpportunityStageCode,
    OpportunityValidationError,
    OpportunityView,
    validate_opportunity_draft,
    validate_opportunity_state,
)
from ...domain.prospect import ProspectStageCode
from ..audit_events import tenant_audit_event
from ..errors import (
    IdempotencyKeyReused,
    InsufficientCapability,
    OpportunityCursorInvalid,
    OpportunityOwnerInactive,
    OpportunityParentArchived,
    OpportunityResourceNotFound,
    OpportunityTransitionInvalid,
    OpportunityVersionConflict,
    ProspectResourceNotFound,
)
from ..ports.clock import Clock
from ..ports.metrics import CrmOpportunityAction, MetricsRecorder, NullMetricsRecorder
from ..ports.opportunity import OpportunityCursor
from ..ports.prospect import ProspectUnitOfWorkFactory
from ..tenancy import TenantContext

_OPEN_SEQUENCE = (
    OpportunityStageCode.DISCOVERY,
    OpportunityStageCode.QUALIFICATION,
    OpportunityStageCode.PROPOSAL,
    OpportunityStageCode.NEGOTIATION,
)


class OpportunityCursorCodec(Protocol):
    def encode(self, cursor: OpportunityCursor, *, scope: str) -> str: ...

    def decode(self, value: str | None, *, scope: str) -> OpportunityCursor | None: ...


@dataclass(frozen=True, slots=True)
class OpportunityPage:
    items: tuple[OpportunityView, ...]
    next_cursor: str | None
    has_more: bool
    aggregates_by_currency: tuple[OpportunityCurrencyAggregate, ...] = ()


class ListOpportunitySummariesUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        prospect_ids: tuple[UUID, ...],
        can_read: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
    ) -> tuple[OpportunityProspectSummary, ...]:
        _require(can_read)
        unique_ids = tuple(dict.fromkeys(prospect_ids))
        if not unique_ids or len(unique_ids) > 100:
            raise OpportunityValidationError("La liste de prospects doit contenir entre 1 et 100 identifiants.")
        if not can_manage and current_membership_id is None:
            raise InsufficientCapability
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.opportunities.summaries_for_prospects(
                unique_ids,
                owner_membership_id=None if can_manage else current_membership_id,
                organization_today=self._clock.now().date(),
            )


class CreateOpportunityUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, metrics: MetricsRecorder | None = None
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self,
        *,
        context: TenantContext,
        draft: OpportunityDraft,
        can_create: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
    ) -> OpportunityView:
        _require(can_create)
        try:
            now = self._clock.now()
            draft = validate_opportunity_draft(draft, organization_today=now.date())
            if not can_manage and (current_membership_id is None or draft.owner_membership_id != current_membership_id):
                raise InsufficientCapability
            fingerprint = _fingerprint("created", draft)
            async with self._unit_of_work_factory(context) as unit_of_work:
                replay = await unit_of_work.opportunity_events.get_by_idempotency_key(
                    event_type=OpportunityEventType.CREATED, idempotency_key=draft.idempotency_key
                )
                if replay is not None:
                    if replay.command_fingerprint != fingerprint:
                        raise IdempotencyKeyReused
                    opportunity = await unit_of_work.opportunities.get(replay.opportunity_id)
                    if opportunity is None:
                        raise OpportunityResourceNotFound
                    return opportunity
                prospect = await unit_of_work.prospects.get(draft.prospect_id)
                _ensure_creatable_prospect(prospect)
                if not await unit_of_work.opportunities.is_active_owner(draft.owner_membership_id):
                    raise OpportunityValidationError("Le responsable de l’opportunité doit être un membre actif.")
                opportunity = await unit_of_work.opportunities.add(
                    draft, organization_id=context.organization_id, actor_id=context.actor_id, now=now
                )
                await unit_of_work.opportunity_events.add(
                    _event(
                        opportunity,
                        context,
                        OpportunityEventType.CREATED,
                        from_stage=None,
                        changed_fields={"name": "changed", "amount": "changed", "currency_code": "changed"},
                        reason_code=None,
                        reason_note=None,
                        idempotency_key=draft.idempotency_key,
                        fingerprint=fingerprint,
                        now=now,
                    )
                )
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        AuditAction.OPPORTUNITY_CREATED,
                        opportunity.id,
                        {
                            "resulting_version": opportunity.version,
                            "stage_code": opportunity.stage_code.value,
                            "currency_code": opportunity.currency_code,
                        },
                    )
                )
                await unit_of_work.commit()
                self._metrics.record_crm_opportunity_command("created", "accepted")
                return opportunity
        except Exception:
            self._metrics.record_crm_opportunity_command("created", "rejected")
            raise


class UpdateOpportunityUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, metrics: MetricsRecorder | None = None
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self,
        *,
        context: TenantContext,
        opportunity_id: UUID,
        expected_version: int,
        changes: dict[str, object],
        idempotency_key: str,
        can_update: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
    ) -> OpportunityView:
        _require(can_update)
        return await _mutate_opportunity(
            unit_of_work_factory=self._unit_of_work_factory,
            clock=self._clock,
            metrics=self._metrics,
            context=context,
            opportunity_id=opportunity_id,
            expected_version=expected_version,
            changes=changes,
            event_type=OpportunityEventType.UPDATED,
            idempotency_key=idempotency_key,
            can_manage=can_manage,
            current_membership_id=current_membership_id,
            reason_code=None,
            reason_note=None,
        )


class TransitionOpportunityUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, metrics: MetricsRecorder | None = None
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self,
        *,
        context: TenantContext,
        opportunity_id: UUID,
        expected_version: int,
        to_stage: OpportunityStageCode,
        reason_code: str | None,
        reason_note: str | None,
        idempotency_key: str,
        can_close: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
    ) -> OpportunityView:
        _require(can_close)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            opportunity = _ensure_visible(await unit_of_work.opportunities.get(opportunity_id))
            _ensure_owner_can_mutate(opportunity, can_manage, current_membership_id)
            if opportunity.stage_code not in OPEN_OPPORTUNITY_STAGES:
                raise OpportunityTransitionInvalid("Une opportunité terminale doit être rouverte explicitement.")
            _ensure_transition(opportunity.stage_code, to_stage)
            changes = _transition_changes(opportunity, to_stage, reason_code, reason_note, now)
        result = await _mutate_opportunity(
            unit_of_work_factory=self._unit_of_work_factory,
            clock=self._clock,
            metrics=self._metrics,
            context=context,
            opportunity_id=opportunity_id,
            expected_version=expected_version,
            changes=changes,
            event_type=OpportunityEventType.STAGE_CHANGED,
            idempotency_key=idempotency_key,
            can_manage=can_manage,
            current_membership_id=current_membership_id,
            reason_code=reason_code,
            reason_note=reason_note,
        )
        self._metrics.record_crm_opportunity_transition(
            opportunity.stage_code.value, result.stage_code.value, "accepted"
        )
        return result


class ReopenOpportunityUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, metrics: MetricsRecorder | None = None
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self,
        *,
        context: TenantContext,
        opportunity_id: UUID,
        expected_version: int,
        reason_code: str,
        reason_note: str | None,
        probability: int,
        idempotency_key: str,
        can_reopen: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
    ) -> OpportunityView:
        _require(can_reopen)
        try:
            reopen_reason = OpportunityReopenReasonCode(reason_code)
        except ValueError as error:
            raise OpportunityTransitionInvalid("Le motif de réouverture est invalide.") from error
        if reopen_reason is OpportunityReopenReasonCode.OTHER and not (reason_note or "").strip():
            raise OpportunityTransitionInvalid("Le motif « autre » exige une note.")
        if not 0 <= probability <= 100:
            raise OpportunityTransitionInvalid("La probabilité de réouverture est invalide.")
        async with self._unit_of_work_factory(context) as unit_of_work:
            opportunity = _ensure_visible(await unit_of_work.opportunities.get(opportunity_id))
            _ensure_owner_can_mutate(opportunity, can_manage, current_membership_id)
            if opportunity.stage_code not in {OpportunityStageCode.WON, OpportunityStageCode.LOST}:
                raise OpportunityTransitionInvalid("Seule une opportunité terminale peut être rouverte.")
            target = (
                OpportunityStageCode.NEGOTIATION
                if opportunity.stage_code is OpportunityStageCode.WON
                else await unit_of_work.opportunity_events.latest_open_stage(opportunity.id)
                or OpportunityStageCode.DISCOVERY
            )
        return await _mutate_opportunity(
            unit_of_work_factory=self._unit_of_work_factory,
            clock=self._clock,
            metrics=self._metrics,
            context=context,
            opportunity_id=opportunity_id,
            expected_version=expected_version,
            changes={
                "stage_code": target,
                "probability": probability,
                "loss_reason_code": None,
                "loss_reason_note": None,
                "closed_at": None,
            },
            event_type=OpportunityEventType.REOPENED,
            idempotency_key=idempotency_key,
            can_manage=can_manage,
            current_membership_id=current_membership_id,
            reason_code=reopen_reason.value,
            reason_note=reason_note,
        )


class GetOpportunityUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        opportunity_id: UUID,
        can_read: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
    ) -> OpportunityView:
        _require(can_read)
        async with self._unit_of_work_factory(context) as unit_of_work:
            opportunity = _ensure_visible(await unit_of_work.opportunities.get(opportunity_id))
            _ensure_owner_readable(opportunity, can_manage, current_membership_id)
            return opportunity


class ListOpportunitiesUseCase:
    def __init__(
        self,
        unit_of_work_factory: ProspectUnitOfWorkFactory,
        clock: Clock,
        cursor_codec: OpportunityCursorCodec,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._cursor_codec = cursor_codec
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self,
        *,
        context: TenantContext,
        can_read: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
        limit: int,
        cursor: str | None = None,
        prospect_id: UUID | None = None,
        owner_membership_id: UUID | None = None,
        stage_codes: tuple[OpportunityStageCode, ...] = (),
        currency_code: str | None = None,
        search_text: str | None = None,
        expected_close_from: date | None = None,
        expected_close_to: date | None = None,
        overdue: bool | None = None,
    ) -> OpportunityPage:
        _require(can_read)
        if not 1 <= limit <= 100:
            raise OpportunityCursorInvalid("La limite est invalide.")
        if not can_manage:
            if current_membership_id is None:
                raise InsufficientCapability
            owner_membership_id = current_membership_id
        scope = _scope(
            context,
            owner_membership_id,
            prospect_id,
            stage_codes,
            currency_code,
            search_text,
            expected_close_from,
            expected_close_to,
            overdue,
        )
        try:
            decoded = self._cursor_codec.decode(cursor, scope=scope)
        except ValueError as error:
            raise OpportunityCursorInvalid from error
        today = self._clock.now().date()
        try:
            async with self._unit_of_work_factory(context) as unit_of_work:
                if prospect_id is not None and await unit_of_work.prospects.get(prospect_id) is None:
                    raise ProspectResourceNotFound
                rows = await unit_of_work.opportunities.list(
                    limit=limit + 1,
                    prospect_id=prospect_id,
                    owner_membership_id=owner_membership_id,
                    stage_codes=stage_codes,
                    currency_code=currency_code,
                    search_text=search_text,
                    expected_close_from=expected_close_from,
                    expected_close_to=expected_close_to,
                    overdue=overdue,
                    organization_today=today,
                    after_expected_close_on=decoded.expected_close_on if decoded else None,
                    after_updated_at=decoded.updated_at if decoded else None,
                    after_id=decoded.item_id if decoded else None,
                )
                aggregates = await unit_of_work.opportunities.aggregate(
                    prospect_id=prospect_id,
                    owner_membership_id=owner_membership_id,
                    stage_codes=stage_codes,
                    currency_code=currency_code,
                    search_text=search_text,
                    expected_close_from=expected_close_from,
                    expected_close_to=expected_close_to,
                    overdue=overdue,
                    organization_today=today,
                )
            has_more = len(rows) > limit
            items = rows[:limit]
            next_cursor = (
                self._cursor_codec.encode(
                    OpportunityCursor(items[-1].expected_close_on, items[-1].updated_at, items[-1].id), scope=scope
                )
                if has_more and items
                else None
            )
            self._metrics.record_crm_opportunity_command("portfolio", "accepted")
            return OpportunityPage(
                items=items, next_cursor=next_cursor, has_more=has_more, aggregates_by_currency=aggregates
            )
        except Exception:
            self._metrics.record_crm_opportunity_command("portfolio", "rejected")
            raise


class ListOpportunityEventsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        opportunity_id: UUID,
        limit: int,
        can_read: bool,
        can_manage: bool,
        current_membership_id: UUID | None,
    ) -> tuple[OpportunityEventView, ...]:
        _require(can_read)
        async with self._unit_of_work_factory(context) as unit_of_work:
            opportunity = _ensure_visible(await unit_of_work.opportunities.get(opportunity_id))
            _ensure_owner_readable(opportunity, can_manage, current_membership_id)
            return await unit_of_work.opportunity_events.list_for_opportunity(opportunity_id, limit=limit)


async def _mutate_opportunity(
    *,
    unit_of_work_factory: ProspectUnitOfWorkFactory,
    clock: Clock,
    metrics: MetricsRecorder,
    context: TenantContext,
    opportunity_id: UUID,
    expected_version: int,
    changes: dict[str, object],
    event_type: OpportunityEventType,
    idempotency_key: str,
    can_manage: bool,
    current_membership_id: UUID | None,
    reason_code: str | None,
    reason_note: str | None,
) -> OpportunityView:
    if not expected_version >= 1 or not idempotency_key.strip():
        raise OpportunityValidationError("La version ou la clé d’idempotence est invalide.")
    action = cast(
        CrmOpportunityAction,
        {
            OpportunityEventType.CREATED: "created",
            OpportunityEventType.UPDATED: "updated",
            OpportunityEventType.STAGE_CHANGED: "stage_changed",
            OpportunityEventType.REOPENED: "reopened",
        }[event_type],
    )
    now = clock.now()
    fingerprint = _fingerprint(action, opportunity_id, expected_version, changes, reason_code, reason_note)
    try:
        async with unit_of_work_factory(context) as unit_of_work:
            opportunity = _ensure_visible(await unit_of_work.opportunities.get_for_update(opportunity_id))
            _ensure_owner_can_mutate(opportunity, can_manage, current_membership_id, changes=changes)
            replay = await unit_of_work.opportunity_events.get_by_idempotency_key(
                event_type=event_type, idempotency_key=idempotency_key
            )
            if replay is not None:
                if replay.command_fingerprint != fingerprint or replay.opportunity_id != opportunity_id:
                    raise IdempotencyKeyReused
                return opportunity
            if opportunity.version != expected_version:
                metrics.record_crm_opportunity_version_conflict(action)
                raise OpportunityVersionConflict(opportunity.version)
            _validate_mutation(opportunity, changes, event_type, now)
            updated = await unit_of_work.opportunities.update(
                opportunity_id, expected_version=expected_version, changes=changes, now=now
            )
            if updated is None:
                metrics.record_crm_opportunity_version_conflict(action)
                raise OpportunityVersionConflict(opportunity.version)
            await unit_of_work.opportunity_events.add(
                _event(
                    updated,
                    context,
                    event_type,
                    from_stage=opportunity.stage_code if event_type is not OpportunityEventType.UPDATED else None,
                    changed_fields={name: "changed" for name in changes},
                    reason_code=reason_code,
                    reason_note=reason_note,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    now=now,
                    from_version=opportunity.version,
                )
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    _audit_action(event_type),
                    updated.id,
                    _audit_metadata(updated, opportunity.stage_code, changes, reason_code),
                )
            )
            await unit_of_work.commit()
            metrics.record_crm_opportunity_command(action, "accepted")
            return updated
    except Exception:
        metrics.record_crm_opportunity_command(action, "rejected")
        raise


def _ensure_creatable_prospect(prospect: object | None) -> None:
    if prospect is None:
        raise ProspectResourceNotFound
    if getattr(prospect, "archived_at", None) is not None:
        raise OpportunityParentArchived
    if getattr(prospect, "stage_code", None) in {ProspectStageCode.WON, ProspectStageCode.LOST}:
        raise OpportunityTransitionInvalid(
            "Le prospect terminal doit être rouvert avant la création d’une opportunité."
        )


def _ensure_visible(opportunity: OpportunityView | None) -> OpportunityView:
    if opportunity is None:
        raise OpportunityResourceNotFound
    return opportunity


def _ensure_owner_readable(opportunity: OpportunityView, can_manage: bool, current_membership_id: UUID | None) -> None:
    if not can_manage and opportunity.owner_membership_id != current_membership_id:
        raise InsufficientCapability


def _ensure_owner_can_mutate(
    opportunity: OpportunityView,
    can_manage: bool,
    current_membership_id: UUID | None,
    *,
    changes: dict[str, object] | None = None,
) -> None:
    _ensure_owner_readable(opportunity, can_manage, current_membership_id)
    if not opportunity.owner_membership_is_active:
        only_reassignment = changes is not None and set(changes) == {"owner_membership_id"}
        if not (can_manage and only_reassignment):
            raise OpportunityOwnerInactive


def _ensure_transition(current: OpportunityStageCode, target: OpportunityStageCode) -> None:
    if target is OpportunityStageCode.LOST:
        return
    if target is OpportunityStageCode.WON:
        if current in {OpportunityStageCode.PROPOSAL, OpportunityStageCode.NEGOTIATION}:
            return
        raise OpportunityTransitionInvalid("Seule une proposition ou négociation peut être gagnée.")
    if target not in OPEN_OPPORTUNITY_STAGES:
        raise OpportunityTransitionInvalid("L’étape cible est invalide.")
    if abs(_OPEN_SEQUENCE.index(current) - _OPEN_SEQUENCE.index(target)) != 1:
        raise OpportunityTransitionInvalid("La transition entre étapes ouvertes doit avancer ou reculer d’un cran.")


def _transition_changes(
    opportunity: OpportunityView,
    target: OpportunityStageCode,
    reason_code: str | None,
    reason_note: str | None,
    now: datetime,
) -> dict[str, object]:
    if target in OPEN_OPPORTUNITY_STAGES:
        if reason_code is not None or reason_note is not None:
            raise OpportunityTransitionInvalid("Une transition ouverte ne porte pas de motif.")
        return {"stage_code": target}
    if target is OpportunityStageCode.WON:
        if reason_code is not None or reason_note is not None:
            raise OpportunityTransitionInvalid("Une opportunité gagnée ne porte pas de motif.")
        return {"stage_code": target, "probability": 100, "closed_at": now}
    try:
        loss_reason = OpportunityLossReasonCode(cast(str, reason_code))
    except (TypeError, ValueError) as error:
        raise OpportunityTransitionInvalid("Le motif de perte est obligatoire et invalide.") from error
    try:
        validate_opportunity_state(
            stage_code=OpportunityStageCode.LOST,
            probability=0,
            loss_reason_code=loss_reason,
            loss_reason_note=reason_note,
            closed_at=now,
        )
    except OpportunityValidationError as error:
        raise OpportunityTransitionInvalid(str(error)) from error
    return {
        "stage_code": OpportunityStageCode.LOST,
        "probability": 0,
        "loss_reason_code": loss_reason,
        "loss_reason_note": reason_note.strip() if reason_note else None,
        "closed_at": now,
    }


def _validate_mutation(
    opportunity: OpportunityView,
    changes: dict[str, object],
    event_type: OpportunityEventType,
    now: datetime,
) -> None:
    if not changes:
        raise OpportunityValidationError("La modification ne contient aucun champ.")
    if event_type is OpportunityEventType.UPDATED:
        if opportunity.stage_code not in OPEN_OPPORTUNITY_STAGES:
            raise OpportunityTransitionInvalid("Une opportunité terminale est en lecture seule jusqu’à sa réouverture.")
        allowed = {"name", "amount", "currency_code", "probability", "expected_close_on", "owner_membership_id"}
        if set(changes).difference(allowed):
            raise OpportunityValidationError("Les champs modifiés sont invalides.")
        if "currency_code" in changes and "amount" not in changes:
            raise OpportunityValidationError("Changer de devise exige de confirmer le montant.")
        draft = OpportunityDraft(
            prospect_id=opportunity.prospect_id,
            owner_membership_id=cast(UUID, changes.get("owner_membership_id", opportunity.owner_membership_id)),
            name=cast(str, changes.get("name", opportunity.name)),
            amount=cast(Decimal, changes.get("amount", opportunity.amount)),
            currency_code=cast(str, changes.get("currency_code", opportunity.currency_code)),
            probability=cast(int, changes.get("probability", opportunity.probability)),
            expected_close_on=cast(date, changes.get("expected_close_on", opportunity.expected_close_on)),
            idempotency_key="validation",
        )
        # Une échéance déjà dépassée reste lisible et modifiable tant que
        # l'utilisateur ne tente pas de la changer. La règle « aujourd'hui ou
        # après » s'applique donc uniquement à une nouvelle échéance.
        validation_today = (
            now.date() if "expected_close_on" in changes else min(now.date(), opportunity.expected_close_on)
        )
        validate_opportunity_draft(draft, organization_today=validation_today)
        if all(getattr(opportunity, name) == value for name, value in changes.items()):
            raise OpportunityValidationError("La modification ne change aucune valeur.")
        return
    stage_code = cast(OpportunityStageCode, changes["stage_code"])
    probability = cast(int, changes.get("probability", opportunity.probability))
    validate_opportunity_state(
        stage_code=stage_code,
        probability=probability,
        loss_reason_code=cast(OpportunityLossReasonCode | None, changes.get("loss_reason_code")),
        loss_reason_note=cast(str | None, changes.get("loss_reason_note")),
        closed_at=cast(datetime | None, changes.get("closed_at")),
    )


def _event(
    opportunity: OpportunityView,
    context: TenantContext,
    event_type: OpportunityEventType,
    *,
    from_stage: OpportunityStageCode | None,
    changed_fields: dict[str, str],
    reason_code: str | None,
    reason_note: str | None,
    idempotency_key: str,
    fingerprint: str,
    now: datetime,
    from_version: int | None = None,
) -> OpportunityEventView:
    return OpportunityEventView(
        id=uuid4(),
        organization_id=context.organization_id,
        prospect_id=opportunity.prospect_id,
        opportunity_id=opportunity.id,
        actor_id=context.actor_id,
        event_type=event_type,
        from_stage=from_stage,
        to_stage=opportunity.stage_code if event_type is not OpportunityEventType.UPDATED else None,
        from_version=from_version if from_version is not None else opportunity.version,
        resulting_version=opportunity.version,
        changed_fields=changed_fields,
        reason_code=reason_code,
        reason_note=reason_note.strip() if reason_note else None,
        idempotency_key=idempotency_key,
        command_fingerprint=fingerprint,
        occurred_at=now,
    )


def _audit_action(event_type: OpportunityEventType) -> AuditAction:
    return {
        OpportunityEventType.CREATED: AuditAction.OPPORTUNITY_CREATED,
        OpportunityEventType.UPDATED: AuditAction.OPPORTUNITY_UPDATED,
        OpportunityEventType.STAGE_CHANGED: AuditAction.OPPORTUNITY_STAGE_CHANGED,
        OpportunityEventType.REOPENED: AuditAction.OPPORTUNITY_REOPENED,
    }[event_type]


def _audit_metadata(
    opportunity: OpportunityView,
    from_stage: OpportunityStageCode,
    changes: dict[str, object],
    reason_code: str | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "resulting_version": opportunity.version,
        "stage_code": opportunity.stage_code.value,
        "changed_fields": list(changes),
    }
    if opportunity.stage_code != from_stage:
        result["from_stage"] = from_stage.value
    if reason_code is not None:
        result["reason_code"] = reason_code
    if "currency_code" in changes:
        result["currency_code"] = opportunity.currency_code
    return result


def _fingerprint(*values: object) -> str:
    return hashlib.sha256(
        json.dumps(values, default=str, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _scope(
    context: TenantContext,
    owner_membership_id: UUID | None,
    prospect_id: UUID | None,
    stage_codes: tuple[OpportunityStageCode, ...],
    currency_code: str | None,
    search_text: str | None,
    expected_close_from: date | None,
    expected_close_to: date | None,
    overdue: bool | None,
) -> str:
    payload = {
        "organization_id": str(context.organization_id),
        "owner_membership_id": str(owner_membership_id) if owner_membership_id else None,
        "prospect_id": str(prospect_id) if prospect_id else None,
        "stage_codes": [stage.value for stage in stage_codes],
        "currency_code": currency_code,
        "search_text": search_text,
        "expected_close_from": expected_close_from.isoformat() if expected_close_from else None,
        "expected_close_to": expected_close_to.isoformat() if expected_close_to else None,
        "overdue": overdue,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _require(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability
