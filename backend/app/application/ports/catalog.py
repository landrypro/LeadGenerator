"""Ports des mutations internes P5.2 du catalogue commercial."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from ...domain.catalog import (
    ContractState,
    CurrencyCode,
    EntitlementKey,
    EntitlementKind,
    EntitlementValue,
    OverrideState,
    PlanCode,
)
from ..tenancy import ActorContext, TenantContext
from .audit import AuditRecorder


class CatalogMutationResultCode(StrEnum):
    CREATED = "created"
    PUBLISHED = "published"
    UPDATED = "updated"
    REPLAYED = "replayed"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    VERSION_CONFLICT = "version_conflict"
    INVALID_TRANSITION = "invalid_transition"
    APPROVAL_REQUIRED = "approval_required"
    INVALID_CONTRACT = "invalid_contract"
    SAFETY_CEILING_EXCEEDED = "safety_ceiling_exceeded"


@dataclass(frozen=True, slots=True)
class CatalogPlanView:
    id: UUID
    code: PlanCode
    state: str
    display_order: int
    version: int


@dataclass(frozen=True, slots=True)
class CatalogPlanVersionView:
    id: UUID
    plan_id: UUID
    version_number: int
    state: str
    currency: CurrencyCode
    billing_cycle: str
    amount_excluding_tax_minor: int
    effective_from: datetime
    effective_until: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class OrganizationPlanContractView:
    id: UUID
    organization_id: UUID
    plan_version_id: UUID
    state: ContractState
    currency: CurrencyCode
    effective_from: datetime
    effective_until: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class PlanContractOverrideView:
    id: UUID
    organization_id: UUID
    contract_id: UUID
    entitlement_key: EntitlementKey
    value_kind: EntitlementKind
    integer_value: int | None
    boolean_value: bool | None
    state: OverrideState
    requested_by_user_id: UUID
    approved_by_user_id: UUID | None
    starts_at: datetime
    ends_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class OrganizationEntitlementDecisionView:
    key: EntitlementKey
    code: str
    value_kind: EntitlementKind | None
    integer_value: int | None
    boolean_value: bool | None
    source: str | None
    reason: str | None
    provenance: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class OrganizationCatalogView:
    contract: OrganizationPlanContractView | None
    entitlements: tuple[OrganizationEntitlementDecisionView, ...]


@dataclass(frozen=True, slots=True)
class CatalogMutationResult:
    code: CatalogMutationResultCode
    plan: CatalogPlanView | None = None
    plan_version: CatalogPlanVersionView | None = None
    contract: OrganizationPlanContractView | None = None
    contract_override: PlanContractOverrideView | None = None
    current_version: int | None = None


class CatalogMutationGateway(Protocol):
    async def create_plan(
        self, *, plan_id: UUID, operation_id: UUID, code: PlanCode, display_order: int, now: datetime
    ) -> CatalogMutationResult: ...

    async def create_plan_version(
        self,
        *,
        version_id: UUID,
        operation_id: UUID,
        plan_id: UUID,
        version_number: int,
        currency: CurrencyCode,
        billing_cycle: str,
        amount_excluding_tax_minor: int,
        effective_from: datetime,
        effective_until: datetime | None,
        entitlements: tuple[EntitlementValue, ...],
        now: datetime,
    ) -> CatalogMutationResult: ...

    async def publish_plan_version(
        self, *, version_id: UUID, operation_id: UUID, expected_version: int, now: datetime
    ) -> CatalogMutationResult: ...

    async def attach_organization_contract(
        self,
        *,
        contract_id: UUID,
        operation_id: UUID,
        organization_id: UUID,
        plan_version_id: UUID,
        state: ContractState,
        effective_from: datetime,
        effective_until: datetime | None,
        now: datetime,
    ) -> CatalogMutationResult: ...

    async def change_contract_state(
        self, *, contract_id: UUID, operation_id: UUID, expected_version: int, state: ContractState, now: datetime
    ) -> CatalogMutationResult: ...

    async def propose_contract_override(
        self,
        *,
        override_id: UUID,
        operation_id: UUID,
        contract_id: UUID,
        value: EntitlementValue,
        justification: str,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> CatalogMutationResult: ...

    async def approve_contract_override(
        self, *, override_id: UUID, operation_id: UUID, expected_version: int, now: datetime
    ) -> CatalogMutationResult: ...

    async def revoke_contract_override(
        self, *, override_id: UUID, operation_id: UUID, expected_version: int, now: datetime
    ) -> CatalogMutationResult: ...


class OrganizationCatalogReader(Protocol):
    async def get_current(self, *, context: TenantContext, now: datetime) -> OrganizationCatalogView: ...


class CatalogAuditedUnitOfWork(Protocol):
    @property
    def mutations(self) -> CatalogMutationGateway: ...

    @property
    def audit(self) -> AuditRecorder: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


CatalogAuditedUnitOfWorkFactory = Callable[[ActorContext], CatalogAuditedUnitOfWork]
