from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ...domain.identity import MembershipRole, MembershipStatus
from ...domain.organization import (
    MemberInvitationView,
    MemberView,
    OrganizationView,
    UpdateMembershipCommand,
    ValidatedCreateMemberInvitation,
    ValidatedUpdateOrganization,
)
from ...domain.provisioning import InvitationDeliveryStatus, InvitationToken
from ..tenancy import ActorContext, TenantContext


class UpdateOrganizationResultCode(StrEnum):
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    NOT_FOUND = "not_found"
    VERSION_CONFLICT = "version_conflict"


class UpdateMembershipResultCode(StrEnum):
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    NOT_FOUND = "not_found"
    VERSION_CONFLICT = "version_conflict"
    LAST_ACTIVE_ADMINISTRATOR = "last_active_administrator"


class CreateMemberInvitationResultCode(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    MEMBERSHIP_ALREADY_ACTIVE = "membership_already_active"
    MEMBERSHIP_REACTIVATION_REQUIRED = "membership_reactivation_required"
    INVITATION_ALREADY_PENDING = "invitation_already_pending"
    ORGANIZATION_NOT_ACTIVE = "organization_not_active"


class MemberInvitationMutationResultCode(StrEnum):
    CREATED = "created"
    REPLAYED = "replayed"
    REVOKED = "revoked"
    ALREADY_REVOKED = "already_revoked"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    NOT_FOUND = "not_found"
    ALREADY_ACCEPTED = "already_accepted"
    RATE_LIMITED = "rate_limited"


class SwitchOrganizationResultCode(StrEnum):
    SWITCHED = "switched"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True, slots=True)
class UpdateOrganizationGatewayResult:
    code: UpdateOrganizationResultCode
    organization: OrganizationView | None = None
    current_version: int | None = None
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdateMembershipGatewayResult:
    code: UpdateMembershipResultCode
    member: MemberView | None = None
    user_version: int | None = None
    current_version: int | None = None
    previous_role: MembershipRole | None = None
    previous_status: MembershipStatus | None = None


@dataclass(frozen=True, slots=True)
class CreateMemberInvitationGatewayResult:
    code: CreateMemberInvitationResultCode
    invitation: MemberInvitationView | None = None
    delivery_attempt_id: UUID | None = None
    revoked_invitation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class MemberInvitationMutationGatewayResult:
    code: MemberInvitationMutationResultCode
    invitation: MemberInvitationView | None = None
    delivery_attempt_id: UUID | None = None
    retry_after_seconds: int = 0
    revoked_invitation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DeliveryFinalizationGatewayResult:
    transitioned: bool
    invitation_id: UUID
    delivery_status: InvitationDeliveryStatus
    delivery_kind: str


@dataclass(frozen=True, slots=True)
class SwitchOrganizationGatewayResult:
    code: SwitchOrganizationResultCode
    organization_id: UUID | None = None
    user_version: int | None = None
    previous_membership_id: UUID | None = None
    new_membership_id: UUID | None = None


class OrganizationAdministrationGateway(Protocol):
    async def get_organization(self, *, context: TenantContext) -> OrganizationView | None: ...

    async def list_members(
        self,
        *,
        context: TenantContext,
        after_created_at: datetime | None,
        after_id: UUID | None,
        limit: int,
    ) -> tuple[MemberView, ...]: ...

    async def list_invitations(
        self,
        *,
        context: TenantContext,
        after_created_at: datetime | None,
        after_id: UUID | None,
        limit: int,
        now: datetime,
    ) -> tuple[MemberInvitationView, ...]: ...

    # Compatibilité transitoire des doubles de test; la composition de production
    # injecte les unités de travail auditées ci-dessous.
    async def update_organization(
        self, *, context: TenantContext, command: ValidatedUpdateOrganization, now: datetime
    ) -> UpdateOrganizationGatewayResult: ...

    async def update_membership(
        self, *, context: TenantContext, membership_id: UUID, command: UpdateMembershipCommand, now: datetime
    ) -> UpdateMembershipGatewayResult: ...

    async def create_invitation(
        self,
        *,
        context: TenantContext,
        command: ValidatedCreateMemberInvitation,
        token: InvitationToken,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
    ) -> CreateMemberInvitationGatewayResult: ...

    async def resend_invitation(
        self,
        *,
        context: TenantContext,
        invitation_id: UUID,
        request_id: UUID,
        token: InvitationToken,
        replacement_invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
        cooldown_seconds: int,
        window_seconds: int,
        max_per_window: int,
    ) -> MemberInvitationMutationGatewayResult: ...

    async def revoke_invitation(
        self, *, context: TenantContext, invitation_id: UUID, now: datetime
    ) -> MemberInvitationMutationGatewayResult: ...

    async def finalize_delivery(
        self,
        *,
        context: TenantContext,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        sent: bool,
        failure_code: str | None,
        now: datetime,
    ) -> DeliveryFinalizationGatewayResult | None: ...

    async def switch_organization(
        self, *, context: ActorContext, membership_id: UUID, now: datetime
    ) -> SwitchOrganizationGatewayResult: ...


class TenantOrganizationMutationGateway(Protocol):
    async def update_organization(
        self,
        *,
        command: ValidatedUpdateOrganization,
        now: datetime,
    ) -> UpdateOrganizationGatewayResult: ...

    async def update_membership(
        self,
        *,
        membership_id: UUID,
        command: UpdateMembershipCommand,
        now: datetime,
    ) -> UpdateMembershipGatewayResult: ...

    async def create_invitation(
        self,
        *,
        command: ValidatedCreateMemberInvitation,
        token: InvitationToken,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
    ) -> CreateMemberInvitationGatewayResult: ...

    async def resend_invitation(
        self,
        *,
        invitation_id: UUID,
        request_id: UUID,
        token: InvitationToken,
        replacement_invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
        cooldown_seconds: int,
        window_seconds: int,
        max_per_window: int,
    ) -> MemberInvitationMutationGatewayResult: ...

    async def revoke_invitation(
        self,
        *,
        invitation_id: UUID,
        now: datetime,
    ) -> MemberInvitationMutationGatewayResult: ...

    async def finalize_delivery(
        self,
        *,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        sent: bool,
        failure_code: str | None,
        now: datetime,
    ) -> DeliveryFinalizationGatewayResult: ...


class ActorOrganizationMutationGateway(Protocol):
    async def switch_organization(
        self,
        *,
        membership_id: UUID,
        now: datetime,
    ) -> SwitchOrganizationGatewayResult: ...


def membership_values(
    role: MembershipRole | None,
    status: MembershipStatus | None,
) -> tuple[str | None, str | None]:
    return role.value if role else None, status.value if status else None
