from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from ...domain.assistant import AssistantIntentCode, AssistantPlanItem, AssistantScopeKind
from ..tenancy import TenantContext


class AssistantProviderUnavailable(RuntimeError):
    pass


class AssistantProtectionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AssistantInterpretationRequest:
    request_id: str
    schema_version: int
    locale: str
    user_text_ephemeral: str
    allowed_intent_codes: tuple[str, ...]
    allowed_playbook_codes: tuple[str, ...]
    maximum_scope_hint: int
    correlation_id: str


class AssistantInterpreterPort(Protocol):
    async def interpret(self, request: AssistantInterpretationRequest) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class AssistantQuotaReservation:
    allowed: bool
    scope: Literal["user", "organization", "budget", "circuit"] | None
    retry_after_seconds: int


class AssistantProtection(Protocol):
    async def reserve(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> AssistantQuotaReservation: ...

    async def record_provider_success(self) -> None: ...

    async def record_provider_failure(self) -> None: ...


@dataclass(frozen=True, slots=True)
class AssistantScopeSnapshot:
    resolved_count: int | None
    organization_enabled: bool
    items: tuple[AssistantPlanItem, ...] = ()
    next_cursor: str | None = None


class AssistantScopeReader(Protocol):
    async def organization_enabled(self, context: TenantContext) -> bool: ...

    async def resolve(
        self,
        context: TenantContext,
        *,
        membership_id: UUID,
        intent_code: AssistantIntentCode,
        scope_kind: AssistantScopeKind,
        collective: bool,
        item_limit: int = 5,
    ) -> AssistantScopeSnapshot: ...


class UnavailableAssistantProtection:
    async def reserve(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> AssistantQuotaReservation:
        del organization_id, user_id, now
        raise AssistantProtectionUnavailable

    async def record_provider_success(self) -> None:
        return None

    async def record_provider_failure(self) -> None:
        return None
