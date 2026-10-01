from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from ...domain.audit import AuditAction
from ...domain.pipeline import (
    PIPELINE_STAGES,
    PipelineStageView,
    PipelineValidationError,
    ProspectStageTransitionView,
    ensure_transition_allowed,
    validate_reopen_reason,
    validate_transition_reason,
)
from ...domain.prospect import ProspectStageCode, ProspectView
from ..audit_events import tenant_audit_event
from ..errors import InsufficientCapability, ProspectResourceNotFound, ProspectVersionConflict
from ..ports.clock import Clock
from ..ports.pagination import CursorCodec
from ..ports.prospect import ProspectUnitOfWorkFactory
from ..tenancy import TenantContext


class PipelineResourceNotFound(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PipelineBoard:
    stages: tuple[PipelineStageView, ...]
    columns: dict[str, tuple[ProspectView, ...]]
    next_cursors: dict[str, str | None]


@dataclass(frozen=True, slots=True)
class PipelineColumnPage:
    items: tuple[ProspectView, ...]
    next_cursor: str | None


class ListPipelineStagesUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(self, *, context: TenantContext, has_capability: bool) -> tuple[PipelineStageView, ...]:
        _require(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            stages = await unit_of_work.pipeline.ensure_default_stages(
                organization_id=context.organization_id, now=self._clock.now()
            )
            await unit_of_work.commit()
            return stages


class GetPipelineBoardUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, cursor_codec: CursorCodec
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._cursor_codec = cursor_codec

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        search_text: str | None,
        owner_id: UUID | None,
        priority: int | None,
    ) -> PipelineBoard:
        _require(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            stages = await unit_of_work.pipeline.ensure_default_stages(
                organization_id=context.organization_id, now=self._clock.now()
            )
            columns: dict[str, tuple[ProspectView, ...]] = {}
            next_cursors: dict[str, str | None] = {}
            for stage in stages:
                rows = await unit_of_work.prospects.list_active(
                    limit=26,
                    include_archived=False,
                    search_text=search_text,
                    owner_id=owner_id,
                    priority=priority,
                    stage_code=stage.code.value,
                )
                items = rows[:25]
                columns[stage.code.value] = items
                next_cursors[stage.code.value] = _next_cursor(rows, items, 25, self._cursor_codec)
            await unit_of_work.commit()
        return PipelineBoard(stages=stages, columns=columns, next_cursors=next_cursors)


class ListPipelineColumnUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, cursor_codec: CursorCodec) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._cursor_codec = cursor_codec

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        stage_code: str,
        cursor: str | None,
        limit: int,
        search_text: str | None,
        owner_id: UUID | None,
        priority: int | None,
    ) -> PipelineColumnPage:
        _require(has_capability)
        if not 1 <= limit <= 25:
            raise ValueError("La limite de chargement du pipeline est invalide.")
        try:
            stage = ProspectStageCode(stage_code)
        except ValueError as error:
            raise PipelineValidationError("L’étape demandée est invalide.") from error
        after_created_at, after_id = self._cursor_codec.decode(cursor)
        async with self._unit_of_work_factory(context) as unit_of_work:
            rows = await unit_of_work.prospects.list_active(
                limit=limit + 1,
                after_created_at=after_created_at,
                after_id=after_id,
                include_archived=False,
                search_text=search_text,
                owner_id=owner_id,
                priority=priority,
                stage_code=stage.value,
            )
        items = rows[:limit]
        return PipelineColumnPage(items=items, next_cursor=_next_cursor(rows, items, limit, self._cursor_codec))


class MoveProspectStageUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        prospect_id: UUID,
        expected_version: int,
        to_stage: str,
        reason_code: str | None,
        reason_note: str | None,
        idempotency_key: str,
        has_capability: bool,
        allow_reopen: bool = False,
    ) -> tuple[ProspectView, ProspectStageTransitionView]:
        _require(has_capability)
        try:
            target = ProspectStageCode(to_stage)
        except ValueError as error:
            raise PipelineValidationError("L’étape cible est invalide.") from error
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            replay = await unit_of_work.pipeline.get_transition_by_idempotency_key(
                prospect_id=prospect_id, idempotency_key=idempotency_key
            )
            if replay is not None:
                prospect = await unit_of_work.prospects.get(prospect_id)
                if prospect is None:
                    raise ProspectResourceNotFound
                return prospect, replay
            prospect = await unit_of_work.prospects.get(prospect_id)
            if prospect is None:
                raise ProspectResourceNotFound
            if prospect.version != expected_version:
                raise ProspectVersionConflict(prospect.version)
            normalized_reason_code: str | None
            normalized_reason_note: str | None
            if allow_reopen:
                if prospect.stage_code not in {ProspectStageCode.WON, ProspectStageCode.LOST}:
                    raise PipelineValidationError("Seuls les prospects gagnés ou perdus peuvent être rouverts.")
                normalized_reason_code, normalized_reason_note = validate_reopen_reason(reason_code or "", reason_note)
            else:
                ensure_transition_allowed(prospect.stage_code, target)
                normalized_reason_code, normalized_reason_note = validate_transition_reason(
                    to_stage=target, reason_code=reason_code, reason_note=reason_note
                )
            updated = await unit_of_work.prospects.change_stage(
                prospect_id,
                expected_version=expected_version,
                from_stage=prospect.stage_code.value,
                to_stage=target.value,
                now=now,
            )
            if updated is None:
                raise ProspectVersionConflict(prospect.version)
            transition = await unit_of_work.pipeline.add_transition(
                organization_id=context.organization_id,
                prospect_id=prospect_id,
                actor_id=context.actor_id,
                from_stage=prospect.stage_code.value,
                to_stage=target.value,
                from_version=prospect.version,
                resulting_version=updated.version,
                reason_code=normalized_reason_code,
                reason_note=normalized_reason_note,
                idempotency_key=idempotency_key,
                command_fingerprint=_fingerprint(
                    prospect_id, expected_version, target.value, normalized_reason_code, normalized_reason_note
                ),
                now=now,
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.PROSPECT_STAGE_CHANGED,
                    prospect_id,
                    {
                        "from_stage": prospect.stage_code.value,
                        "to_stage": target.value,
                        "from_version": prospect.version,
                        "resulting_version": updated.version,
                        **({"reason_code": normalized_reason_code} if normalized_reason_code else {}),
                    },
                )
            )
            await unit_of_work.commit()
            return updated, transition


class ReopenProspectUseCase:
    def __init__(self, move: MoveProspectStageUseCase, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._move = move
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        prospect_id: UUID,
        expected_version: int,
        reason_code: str,
        reason_note: str | None,
        idempotency_key: str,
        has_capability: bool,
    ) -> tuple[ProspectView, ProspectStageTransitionView]:
        _require(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            prospect = await unit_of_work.prospects.get(prospect_id)
            if prospect is None:
                raise ProspectResourceNotFound
            history = await unit_of_work.pipeline.list_transitions(prospect_id, limit=1)
        target = (
            history[0].from_stage
            if history and prospect.stage_code is ProspectStageCode.LOST
            else ProspectStageCode.NEGOTIATION
        )
        return await self._move.execute(
            context=context,
            prospect_id=prospect_id,
            expected_version=expected_version,
            to_stage=target.value,
            reason_code=reason_code,
            reason_note=reason_note,
            idempotency_key=idempotency_key,
            has_capability=has_capability,
            allow_reopen=True,
        )


class ListProspectStageTransitionsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self, *, context: TenantContext, prospect_id: UUID, has_capability: bool
    ) -> tuple[ProspectStageTransitionView, ...]:
        _require(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            if await unit_of_work.prospects.get(prospect_id) is None:
                raise ProspectResourceNotFound
            return await unit_of_work.pipeline.list_transitions(prospect_id, limit=100)


class UpdatePipelineStageUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        stage_code: str,
        expected_version: int,
        color_token: str | None,
        labels: dict[str, str] | None,
        has_capability: bool,
    ) -> PipelineStageView:
        _require(has_capability)
        try:
            stage = ProspectStageCode(stage_code)
        except ValueError as error:
            raise PipelineValidationError("L’étape cible est invalide.") from error
        if stage not in PIPELINE_STAGES:
            raise PipelineValidationError("Cette étape ne peut pas être configurée.")
        if color_token is not None and not 1 <= len(color_token.strip()) <= 32:
            raise PipelineValidationError("La couleur de l’étape est invalide.")
        if labels is not None and (
            set(labels) - {"fr-CA", "en-CA"} or any(not 1 <= len(value.strip()) <= 80 for value in labels.values())
        ):
            raise PipelineValidationError("Les libellés de l’étape sont invalides.")
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            await unit_of_work.pipeline.ensure_default_stages(organization_id=context.organization_id, now=now)
            updated = await unit_of_work.pipeline.update_stage(
                stage.value,
                expected_version=expected_version,
                color_token=color_token.strip() if color_token else None,
                labels=labels,
                now=now,
            )
            if updated is None:
                raise ProspectVersionConflict(expected_version)
            changed_fields = tuple(
                name for name, value in (("color_token", color_token), ("labels", labels)) if value is not None
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.PIPELINE_STAGE_SETTINGS_UPDATED,
                    context.organization_id,
                    {"stage_code": stage.value, "changed_fields": changed_fields},
                )
            )
            await unit_of_work.commit()
            return updated


def _require(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability


def _next_cursor(
    rows: tuple[ProspectView, ...], items: tuple[ProspectView, ...], limit: int, cursor_codec: CursorCodec
) -> str | None:
    if len(rows) <= limit or not items:
        return None
    last = items[-1]
    return cursor_codec.encode(last.created_at, last.id)


def _fingerprint(prospect_id: UUID, version: int, stage: str, reason_code: str | None, reason_note: str | None) -> str:
    value = json.dumps(
        [str(prospect_id), version, stage, reason_code, reason_note], separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
