from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from ...domain.opportunity import (
    OpportunityCurrencyAggregate,
    OpportunityDraft,
    OpportunityEventType,
    OpportunityEventView,
    OpportunityProspectSummary,
    OpportunityStageCode,
    OpportunityView,
)


@dataclass(frozen=True, slots=True)
class OpportunityCursor:
    """Clé de reprise du portefeuille, indépendante de son codec de transport."""

    expected_close_on: date
    updated_at: datetime
    item_id: UUID


class OpportunityRepository(Protocol):
    async def add(
        self, draft: OpportunityDraft, *, organization_id: UUID, actor_id: UUID, now: datetime
    ) -> OpportunityView: ...

    async def get(self, opportunity_id: UUID) -> OpportunityView | None: ...

    async def get_for_update(self, opportunity_id: UUID) -> OpportunityView | None: ...

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[OpportunityView, ...]: ...

    async def list(
        self,
        *,
        limit: int,
        prospect_id: UUID | None = None,
        owner_membership_id: UUID | None = None,
        stage_codes: tuple[OpportunityStageCode, ...] = (),
        currency_code: str | None = None,
        search_text: str | None = None,
        expected_close_from: date | None = None,
        expected_close_to: date | None = None,
        overdue: bool | None = None,
        organization_today: date | None = None,
        after_expected_close_on: date | None = None,
        after_updated_at: datetime | None = None,
        after_id: UUID | None = None,
    ) -> tuple[OpportunityView, ...]: ...

    async def aggregate(
        self,
        *,
        prospect_id: UUID | None = None,
        owner_membership_id: UUID | None = None,
        stage_codes: tuple[OpportunityStageCode, ...] = (),
        currency_code: str | None = None,
        search_text: str | None = None,
        expected_close_from: date | None = None,
        expected_close_to: date | None = None,
        overdue: bool | None = None,
        organization_today: date,
    ) -> tuple[OpportunityCurrencyAggregate, ...]: ...

    async def update(
        self,
        opportunity_id: UUID,
        *,
        expected_version: int,
        changes: Mapping[str, object],
        now: datetime,
    ) -> OpportunityView | None: ...

    async def is_active_owner(self, membership_id: UUID) -> bool: ...

    async def summaries_for_prospects(
        self,
        prospect_ids: tuple[UUID, ...],
        *,
        owner_membership_id: UUID | None,
        organization_today: date,
    ) -> tuple[OpportunityProspectSummary, ...]: ...


class OpportunityEventRepository(Protocol):
    async def add(self, event: OpportunityEventView) -> OpportunityEventView: ...

    async def get_by_idempotency_key(
        self, *, event_type: OpportunityEventType, idempotency_key: str
    ) -> OpportunityEventView | None: ...

    async def list_for_opportunity(self, opportunity_id: UUID, *, limit: int) -> tuple[OpportunityEventView, ...]: ...

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[OpportunityEventView, ...]: ...

    async def latest_open_stage(self, opportunity_id: UUID) -> OpportunityStageCode | None: ...
