"""Consultation plateforme des projections Billing, sans action financière."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from ..errors import InsufficientCapability, ProvisioningResourceNotFound
from ..ports.manual_billing_grants import ManualBillingGrantOption, ManualBillingGrantView
from ..tenancy import ActorContext


@dataclass(frozen=True, slots=True)
class PlatformBillingOrganization:
    id: UUID
    name: str
    organization_status: str
    plan_code: str | None
    version_number: int | None
    currency: str | None
    subscription_state: str | None
    contract_state: str | None
    source: str
    current_period_end: datetime | None
    cancel_at_period_end: bool
    reconciliation_status: str
    manual_grant_state: str | None = None


@dataclass(frozen=True, slots=True)
class PlatformBillingEvent:
    event_type: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PlatformBillingIntervention:
    kind: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlatformBillingDetail:
    organization: PlatformBillingOrganization
    events: tuple[PlatformBillingEvent, ...]
    interventions: tuple[PlatformBillingIntervention, ...]
    manual_grant: ManualBillingGrantView | None = None


@dataclass(frozen=True, slots=True)
class PlatformBillingPage:
    items: tuple[PlatformBillingOrganization, ...]
    next_cursor: str | None


class PlatformBillingReader(Protocol):
    async def list_organizations(
        self,
        *,
        context: ActorContext,
        after: UUID | None,
        limit: int,
        state: str | None,
        source: str | None,
    ) -> PlatformBillingPage: ...

    async def get_organization(
        self, *, context: ActorContext, organization_id: UUID
    ) -> PlatformBillingDetail | None: ...

    async def list_manual_grant_options(self, *, context: ActorContext) -> tuple[ManualBillingGrantOption, ...]: ...


class PlatformBillingConsultationUseCase:
    def __init__(self, reader: PlatformBillingReader) -> None:
        self._reader = reader

    async def list(
        self,
        *,
        context: ActorContext,
        has_platform_capability: bool,
        cursor: str | None,
        limit: int,
        state: str | None,
        source: str | None,
    ) -> PlatformBillingPage:
        self._require(has_platform_capability)
        if not 1 <= limit <= 100:
            raise ValueError("La limite doit être comprise entre 1 et 100.")
        after = UUID(cursor) if cursor else None
        return await self._reader.list_organizations(
            context=context, after=after, limit=limit, state=state or None, source=source or None
        )

    async def get(
        self, *, context: ActorContext, has_platform_capability: bool, organization_id: UUID
    ) -> PlatformBillingDetail:
        self._require(has_platform_capability)
        detail = await self._reader.get_organization(context=context, organization_id=organization_id)
        if detail is None:
            raise ProvisioningResourceNotFound
        return detail

    async def list_manual_grant_options(
        self, *, context: ActorContext, has_platform_capability: bool
    ) -> tuple[ManualBillingGrantOption, ...]:
        self._require(has_platform_capability)
        return await self._reader.list_manual_grant_options(context=context)

    @staticmethod
    def _require(has_platform_capability: bool) -> None:
        if not has_platform_capability:
            raise InsufficientCapability
