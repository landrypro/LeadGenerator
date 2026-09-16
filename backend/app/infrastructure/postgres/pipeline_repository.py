from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.ports.prospect import PipelineRepository
from ...domain.pipeline import (
    DEFAULT_STAGE_COLORS,
    DEFAULT_STAGE_LABELS,
    PIPELINE_STAGES,
    PipelineStageView,
    ProspectStageTransitionView,
)
from ...domain.prospect import ProspectStageCode


class SqlAlchemyPipelineRepository(PipelineRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_stages(self) -> tuple[PipelineStageView, ...]:
        rows = (
            (await self._session.execute(text("SELECT * FROM public.pipeline_stage_settings ORDER BY position ASC")))
            .mappings()
            .all()
        )
        return tuple(_stage_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def ensure_default_stages(self, *, organization_id: UUID, now: datetime) -> tuple[PipelineStageView, ...]:
        for position, stage in enumerate(PIPELINE_STAGES, start=1):
            await self._session.execute(
                text(
                    """
                    INSERT INTO public.pipeline_stage_settings (
                        id, organization_id, stage_code, position, color_token, labels, created_at, updated_at
                    ) VALUES (
                        :id, :organization_id, :stage_code, :position, :color_token, CAST(:labels AS jsonb), :now, :now
                    ) ON CONFLICT (organization_id, stage_code) DO NOTHING
                    """
                ),
                {
                    "id": uuid4(),
                    "organization_id": organization_id,
                    "stage_code": stage.value,
                    "position": position,
                    "color_token": DEFAULT_STAGE_COLORS[stage],
                    "labels": json.dumps(DEFAULT_STAGE_LABELS[stage]),
                    "now": now,
                },
            )
        return await self.list_stages()

    async def update_stage(
        self,
        stage_code: str,
        *,
        expected_version: int,
        color_token: str | None,
        labels: dict[str, str] | None,
        now: datetime,
    ) -> PipelineStageView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                    UPDATE public.pipeline_stage_settings
                    SET color_token = COALESCE(:color_token, color_token),
                        labels = COALESCE(CAST(:labels AS jsonb), labels),
                        updated_at = :now,
                        version = version + 1
                    WHERE stage_code = :stage_code AND version = :expected_version
                    RETURNING *
                    """
                    ),
                    {
                        "stage_code": stage_code,
                        "expected_version": expected_version,
                        "color_token": color_token,
                        "labels": json.dumps(labels) if labels is not None else None,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _stage_from_row(cast(Mapping[str, object], row)) if row else None

    async def add_transition(
        self,
        *,
        organization_id: UUID,
        prospect_id: UUID,
        actor_id: UUID,
        from_stage: str,
        to_stage: str,
        from_version: int,
        resulting_version: int,
        reason_code: str | None,
        reason_note: str | None,
        idempotency_key: str,
        command_fingerprint: str,
        now: datetime,
    ) -> ProspectStageTransitionView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                    INSERT INTO public.prospect_stage_transitions (
                        id, organization_id, prospect_id, actor_id, from_stage, to_stage,
                        from_version, resulting_version, reason_code, reason_note,
                        idempotency_key, command_fingerprint, occurred_at
                    ) VALUES (
                        :id, :organization_id, :prospect_id, :actor_id, :from_stage, :to_stage,
                        :from_version, :resulting_version, :reason_code, :reason_note,
                        :idempotency_key, :command_fingerprint, :now
                    ) RETURNING *
                    """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": organization_id,
                        "prospect_id": prospect_id,
                        "actor_id": actor_id,
                        "from_stage": from_stage,
                        "to_stage": to_stage,
                        "from_version": from_version,
                        "resulting_version": resulting_version,
                        "reason_code": reason_code,
                        "reason_note": reason_note,
                        "idempotency_key": idempotency_key,
                        "command_fingerprint": command_fingerprint,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _transition_from_row(cast(Mapping[str, object], row))

    async def get_transition_by_idempotency_key(
        self, *, prospect_id: UUID, idempotency_key: str
    ) -> ProspectStageTransitionView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        "SELECT * FROM public.prospect_stage_transitions WHERE prospect_id = :prospect_id AND idempotency_key = :idempotency_key"
                    ),
                    {"prospect_id": prospect_id, "idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _transition_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_transitions(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectStageTransitionView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        "SELECT * FROM public.prospect_stage_transitions WHERE prospect_id = :prospect_id ORDER BY occurred_at DESC, id DESC LIMIT :limit"
                    ),
                    {"prospect_id": prospect_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_transition_from_row(cast(Mapping[str, object], row)) for row in rows)


def _stage_from_row(row: Mapping[str, object]) -> PipelineStageView:
    return PipelineStageView(
        code=ProspectStageCode(str(row["stage_code"])),
        position=int(cast(int, row["position"])),
        color_token=str(row["color_token"]),
        labels=dict(cast(Mapping[str, str], row["labels"])),
        version=int(cast(int, row["version"])),
    )


def _transition_from_row(row: Mapping[str, object]) -> ProspectStageTransitionView:
    return ProspectStageTransitionView(
        id=cast(UUID, row["id"]),
        prospect_id=cast(UUID, row["prospect_id"]),
        actor_id=cast(UUID, row["actor_id"]),
        from_stage=ProspectStageCode(str(row["from_stage"])),
        to_stage=ProspectStageCode(str(row["to_stage"])),
        from_version=int(cast(int, row["from_version"])),
        resulting_version=int(cast(int, row["resulting_version"])),
        reason_code=cast(str | None, row["reason_code"]),
        reason_note=cast(str | None, row["reason_note"]),
        occurred_at=cast(datetime, row["occurred_at"]),
    )
