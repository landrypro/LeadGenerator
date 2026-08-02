from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ...domain.provisioning import (
    AcceptedInvitation,
    InvitationMessage,
    InvitationPreview,
    InvitationToken,
    ProvisioningView,
    ValidatedProvisionOrganization,
)
from ..tenancy import ActorContext


class ProvisionResultCode(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


class ResendResultCode(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    NOT_FOUND = "not_found"
    ALREADY_ACCEPTED = "already_accepted"
    RATE_LIMITED = "rate_limited"


class RevokeResultCode(StrEnum):
    REVOKED = "revoked"
    ALREADY_REVOKED = "already_revoked"
    NOT_FOUND = "not_found"
    ALREADY_ACCEPTED = "already_accepted"


class AcceptanceResultCode(StrEnum):
    ACCEPTED = "accepted"
    INVALID = "invalid"
    EXISTING_ACCOUNT = "existing_account"
    ACCOUNT_MISMATCH = "account_mismatch"
    MEMBERSHIP_REACTIVATION_REQUIRED = "membership_reactivation_required"


@dataclass(frozen=True, slots=True)
class ProvisionGatewayResult:
    code: ProvisionResultCode
    view: ProvisioningView | None = None
    delivery_attempt_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ResendGatewayResult:
    code: ResendResultCode
    view: ProvisioningView | None = None
    delivery_attempt_id: UUID | None = None
    retry_after_seconds: int = 0


@dataclass(frozen=True, slots=True)
class RevokeGatewayResult:
    code: RevokeResultCode
    view: ProvisioningView | None = None


@dataclass(frozen=True, slots=True)
class AcceptanceGatewayResult:
    code: AcceptanceResultCode
    accepted: AcceptedInvitation | None = None


class PlatformProvisioningGateway(Protocol):
    async def provision(
        self,
        *,
        context: ActorContext,
        command: ValidatedProvisionOrganization,
        token: InvitationToken,
        organization_id: UUID,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
    ) -> ProvisionGatewayResult: ...

    async def list_organizations(
        self,
        *,
        context: ActorContext,
        before_created_at: datetime | None,
        before_id: UUID | None,
        limit: int,
        now: datetime,
    ) -> tuple[ProvisioningView, ...]: ...

    async def prepare_resend(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        request_id: UUID,
        token: InvitationToken,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
        cooldown_seconds: int,
        window_seconds: int,
        max_per_window: int,
    ) -> ResendGatewayResult: ...

    async def revoke_initial_invitation(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        now: datetime,
    ) -> RevokeGatewayResult: ...

    async def finalize_delivery(
        self,
        *,
        context: ActorContext,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        sent: bool,
        failure_code: str | None,
        now: datetime,
    ) -> None: ...


class InvitationAcceptanceGateway(Protocol):
    async def preview(self, *, token_hash: str, now: datetime) -> InvitationPreview | None: ...

    async def accept_new_account(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        membership_id: UUID,
        display_name: str,
        password_hash: str,
        now: datetime,
    ) -> AcceptanceGatewayResult: ...

    async def accept_existing_account(
        self,
        *,
        context: ActorContext,
        token_hash: str,
        membership_id: UUID,
        now: datetime,
    ) -> AcceptanceGatewayResult: ...


class InvitationTokenGenerator(Protocol):
    def generate(self) -> InvitationToken: ...


class InvitationDelivery(Protocol):
    @property
    def is_configured(self) -> bool: ...

    async def send(self, message: InvitationMessage) -> None: ...


@dataclass(frozen=True, slots=True)
class InvitationLimitStatus:
    blocked: bool
    retry_after_seconds: int = 0


class InvitationRateLimiter(Protocol):
    async def consume(self, *, client_address: str, token_hash: str) -> InvitationLimitStatus: ...
