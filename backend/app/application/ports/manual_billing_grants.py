"""Ports du parcours d'exception Billing sandbox.

Les droits manuels sont volontairement distincts des commandes, clients,
abonnements et preuves de paiement des fournisseurs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from ...domain.billing import ManualBillingGrantReasonCode, ManualBillingGrantState
from ..tenancy import ActorContext
from .audit import AuditRecorder


class ManualBillingGrantMutationCode(StrEnum):
    CREATED = "created"
    APPROVED = "approved"
    REVOKED = "revoked"
    REPLAYED = "replayed"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    VERSION_CONFLICT = "version_conflict"
    APPROVAL_REQUIRED = "approval_required"
    INVALID_STATE = "invalid_state"
    CATALOG_VERSION_UNAVAILABLE = "catalog_version_unavailable"
    COMMAND_CONFLICT = "command_conflict"


@dataclass(frozen=True, slots=True)
class ManualBillingGrantOption:
    plan_version_id: UUID
    code: str
    version_number: int
    currency: str
    amount_minor: int


@dataclass(frozen=True, slots=True)
class ManualBillingGrantView:
    id: UUID
    organization_id: UUID
    plan_version_id: UUID
    plan_code: str
    version_number: int
    currency: str
    reason_code: ManualBillingGrantReasonCode
    duration_days: int
    state: ManualBillingGrantState
    starts_at: datetime | None
    ends_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class ManualBillingGrantMutationResult:
    code: ManualBillingGrantMutationCode
    grant: ManualBillingGrantView | None = None
    current_version: int | None = None


class ManualBillingGrantMutationGateway(Protocol):
    async def list_options(self, *, now: datetime) -> tuple[ManualBillingGrantOption, ...]: ...

    async def propose(
        self,
        *,
        grant_id: UUID,
        operation_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        organization_id: UUID,
        plan_version_id: UUID,
        reason_code: ManualBillingGrantReasonCode,
        duration_days: int,
        now: datetime,
    ) -> ManualBillingGrantMutationResult: ...

    async def approve(
        self,
        *,
        grant_id: UUID,
        operation_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        expected_version: int,
        now: datetime,
    ) -> ManualBillingGrantMutationResult: ...

    async def revoke(
        self,
        *,
        grant_id: UUID,
        operation_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        expected_version: int,
        now: datetime,
    ) -> ManualBillingGrantMutationResult: ...


class ManualBillingGrantAuditedUnitOfWork(Protocol):
    @property
    def mutations(self) -> ManualBillingGrantMutationGateway: ...

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


ManualBillingGrantAuditedUnitOfWorkFactory = Callable[[ActorContext], ManualBillingGrantAuditedUnitOfWork]
