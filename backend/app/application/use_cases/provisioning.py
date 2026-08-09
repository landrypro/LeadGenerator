from __future__ import annotations

import base64
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from ...domain.audit import AuditAction
from ...domain.provisioning import (
    InvitationDeliveryStatus,
    InvitationMessage,
    ProvisioningView,
    ProvisionOrganizationCommand,
    validate_provision_organization,
)
from ..audit_events import platform_audit_event
from ..errors import (
    IdempotencyKeyReused,
    InsufficientCapability,
    InvitationAlreadyAccepted,
    InvitationDeliveryFailed,
    InvitationDeliveryUnavailable,
    InvitationRateLimited,
    ProvisioningOutcomeUnknown,
    ProvisioningResourceNotFound,
    ProvisioningServiceUnavailable,
)
from ..ports import (
    Clock,
    InvitationDelivery,
    InvitationTokenGenerator,
    PlatformProvisioningGateway,
    ProvisionResultCode,
    ResendResultCode,
    RevokeResultCode,
)
from ..ports.audit import PlatformAuditedUnitOfWorkFactory
from ..tenancy import ActorContext


@dataclass(frozen=True, slots=True)
class PlatformOrganizationPage:
    items: tuple[ProvisioningView, ...]
    next_cursor: str | None


class CreateOrganizationUseCase:
    def __init__(
        self,
        gateway: PlatformProvisioningGateway,
        token_generator: InvitationTokenGenerator,
        delivery: InvitationDelivery,
        clock: Clock,
        *,
        public_app_url: str,
        invitation_ttl_seconds: int,
        audited_unit_of_work_factory: PlatformAuditedUnitOfWorkFactory | None = None,
    ) -> None:
        self._gateway = gateway
        self._token_generator = token_generator
        self._delivery = delivery
        self._clock = clock
        self._public_app_url = public_app_url.rstrip("/")
        self._invitation_ttl_seconds = invitation_ttl_seconds
        self._audited_unit_of_work_factory = audited_unit_of_work_factory

    async def execute(
        self,
        *,
        context: ActorContext,
        command: ProvisionOrganizationCommand,
        has_platform_capability: bool,
    ) -> ProvisioningView:
        _require_platform(has_platform_capability)
        if not self._delivery.is_configured:
            raise InvitationDeliveryUnavailable
        validated = validate_provision_organization(command)
        now = self._clock.now()
        token = self._token_generator.generate()
        organization_id = uuid4()
        invitation_id = uuid4()
        delivery_attempt_id = uuid4()
        if self._audited_unit_of_work_factory is None:
            result = await self._gateway.provision(
                context=context,
                command=validated,
                token=token,
                organization_id=organization_id,
                invitation_id=invitation_id,
                delivery_attempt_id=delivery_attempt_id,
                expires_at=now + timedelta(seconds=self._invitation_ttl_seconds),
                now=now,
            )
        else:
            async with self._audited_unit_of_work_factory(context) as unit_of_work:
                result = await unit_of_work.mutations.provision(
                    command=validated,
                    token=token,
                    organization_id=organization_id,
                    invitation_id=invitation_id,
                    delivery_attempt_id=delivery_attempt_id,
                    expires_at=now + timedelta(seconds=self._invitation_ttl_seconds),
                    now=now,
                )
                if result.code is ProvisionResultCode.CREATED and result.view is None:
                    raise ProvisioningServiceUnavailable("Le provisioning n’a retourné aucune ressource.")
                if result.code is ProvisionResultCode.CREATED and result.delivery_attempt_id is None:
                    raise ProvisioningOutcomeUnknown
                if result.code is ProvisionResultCode.CREATED and result.view is not None:
                    await unit_of_work.audit.record(
                        platform_audit_event(
                            context,
                            AuditAction.ORGANIZATION_PROVISIONED,
                            result.view.organization.id,
                            organization_id=result.view.organization.id,
                        )
                    )
                    await unit_of_work.audit.record(
                        platform_audit_event(
                            context,
                            AuditAction.INITIAL_INVITATION_CREATED,
                            result.view.first_invitation.id,
                            {
                                "role": result.view.first_invitation.role.value,
                                "invitation_kind": "initial_administrator",
                                "delivery_status": "pending",
                            },
                            organization_id=result.view.organization.id,
                        )
                    )
                await unit_of_work.commit()
        if result.code is ProvisionResultCode.IDEMPOTENCY_CONFLICT:
            raise IdempotencyKeyReused
        if result.view is None:
            raise ProvisioningServiceUnavailable("Le provisioning n’a retourné aucune ressource.")
        if result.code is ProvisionResultCode.REPLAYED:
            return result.view
        if result.delivery_attempt_id is None:
            raise ProvisioningOutcomeUnknown
        return await _deliver_invitation(
            gateway=self._gateway,
            delivery=self._delivery,
            public_app_url=self._public_app_url,
            clock=self._clock,
            context=context,
            view=result.view,
            delivery_attempt_id=result.delivery_attempt_id,
            raw_token=token.raw,
            audited_unit_of_work_factory=self._audited_unit_of_work_factory,
        )


class ListPlatformOrganizationsUseCase:
    def __init__(self, gateway: PlatformProvisioningGateway, clock: Clock) -> None:
        self._gateway = gateway
        self._clock = clock

    async def execute(
        self,
        *,
        context: ActorContext,
        has_platform_capability: bool,
        cursor: str | None,
        limit: int,
    ) -> PlatformOrganizationPage:
        _require_platform(has_platform_capability)
        if not 1 <= limit <= 100:
            raise ValueError("La limite doit être comprise entre 1 et 100.")
        before_created_at, before_id = _decode_cursor(cursor)
        rows = await self._gateway.list_organizations(
            context=context,
            before_created_at=before_created_at,
            before_id=before_id,
            limit=limit + 1,
            now=self._clock.now(),
        )
        items = rows[:limit]
        next_cursor = None
        if len(rows) > limit and items:
            last = items[-1].organization
            next_cursor = _encode_cursor(last.created_at, last.id)
        return PlatformOrganizationPage(items=items, next_cursor=next_cursor)


class ResendInitialInvitationUseCase:
    def __init__(
        self,
        gateway: PlatformProvisioningGateway,
        token_generator: InvitationTokenGenerator,
        delivery: InvitationDelivery,
        clock: Clock,
        *,
        public_app_url: str,
        invitation_ttl_seconds: int,
        cooldown_seconds: int,
        window_seconds: int,
        max_per_window: int,
        audited_unit_of_work_factory: PlatformAuditedUnitOfWorkFactory | None = None,
    ) -> None:
        self._gateway = gateway
        self._token_generator = token_generator
        self._delivery = delivery
        self._clock = clock
        self._public_app_url = public_app_url.rstrip("/")
        self._invitation_ttl_seconds = invitation_ttl_seconds
        self._cooldown_seconds = cooldown_seconds
        self._window_seconds = window_seconds
        self._max_per_window = max_per_window
        self._audited_unit_of_work_factory = audited_unit_of_work_factory

    async def execute(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        resend_request_id: UUID,
        has_platform_capability: bool,
    ) -> ProvisioningView:
        _require_platform(has_platform_capability)
        if not self._delivery.is_configured:
            raise InvitationDeliveryUnavailable
        now = self._clock.now()
        token = self._token_generator.generate()
        invitation_id = uuid4()
        delivery_attempt_id = uuid4()
        if self._audited_unit_of_work_factory is None:
            result = await self._gateway.prepare_resend(
                context=context,
                organization_id=organization_id,
                request_id=resend_request_id,
                token=token,
                invitation_id=invitation_id,
                delivery_attempt_id=delivery_attempt_id,
                expires_at=now + timedelta(seconds=self._invitation_ttl_seconds),
                now=now,
                cooldown_seconds=self._cooldown_seconds,
                window_seconds=self._window_seconds,
                max_per_window=self._max_per_window,
            )
        else:
            async with self._audited_unit_of_work_factory(context) as unit_of_work:
                result = await unit_of_work.mutations.prepare_resend(
                    organization_id=organization_id,
                    request_id=resend_request_id,
                    token=token,
                    invitation_id=invitation_id,
                    delivery_attempt_id=delivery_attempt_id,
                    expires_at=now + timedelta(seconds=self._invitation_ttl_seconds),
                    now=now,
                    cooldown_seconds=self._cooldown_seconds,
                    window_seconds=self._window_seconds,
                    max_per_window=self._max_per_window,
                )
                if result.code is ResendResultCode.CREATED and result.view is None:
                    raise ProvisioningServiceUnavailable("Le renvoi n’a retourné aucune invitation.")
                if result.code is ResendResultCode.CREATED and result.delivery_attempt_id is None:
                    raise ProvisioningOutcomeUnknown
                if result.code is ResendResultCode.CREATED and result.view is not None:
                    if result.revoked_invitation_id is not None:
                        await unit_of_work.audit.record(
                            platform_audit_event(
                                context,
                                AuditAction.INITIAL_INVITATION_REVOKED,
                                result.revoked_invitation_id,
                                organization_id=organization_id,
                            )
                        )
                    await unit_of_work.audit.record(
                        platform_audit_event(
                            context,
                            AuditAction.INITIAL_INVITATION_RESEND_REQUESTED,
                            result.view.first_invitation.id,
                            {"delivery_attempt_id": delivery_attempt_id},
                            organization_id=organization_id,
                        )
                    )
                await unit_of_work.commit()
        if result.code is ResendResultCode.IDEMPOTENCY_CONFLICT:
            raise IdempotencyKeyReused
        if result.code is ResendResultCode.NOT_FOUND:
            raise ProvisioningResourceNotFound
        if result.code is ResendResultCode.ALREADY_ACCEPTED:
            raise InvitationAlreadyAccepted
        if result.code is ResendResultCode.RATE_LIMITED:
            raise InvitationRateLimited(result.retry_after_seconds)
        if result.view is None:
            raise ProvisioningServiceUnavailable("Le renvoi n’a retourné aucune invitation.")
        if result.code is ResendResultCode.REPLAYED:
            return result.view
        if result.delivery_attempt_id is None:
            raise ProvisioningOutcomeUnknown
        return await _deliver_invitation(
            gateway=self._gateway,
            delivery=self._delivery,
            public_app_url=self._public_app_url,
            clock=self._clock,
            context=context,
            view=result.view,
            delivery_attempt_id=result.delivery_attempt_id,
            raw_token=token.raw,
            audited_unit_of_work_factory=self._audited_unit_of_work_factory,
        )


class RevokeInitialInvitationUseCase:
    def __init__(
        self,
        gateway: PlatformProvisioningGateway,
        clock: Clock,
        audited_unit_of_work_factory: PlatformAuditedUnitOfWorkFactory | None = None,
    ) -> None:
        self._gateway = gateway
        self._clock = clock
        self._audited_unit_of_work_factory = audited_unit_of_work_factory

    async def execute(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        has_platform_capability: bool,
    ) -> ProvisioningView:
        _require_platform(has_platform_capability)
        if self._audited_unit_of_work_factory is None:
            result = await self._gateway.revoke_initial_invitation(
                context=context, organization_id=organization_id, now=self._clock.now()
            )
        else:
            async with self._audited_unit_of_work_factory(context) as unit_of_work:
                result = await unit_of_work.mutations.revoke_initial_invitation(
                    organization_id=organization_id, now=self._clock.now()
                )
                if result.code is RevokeResultCode.REVOKED and result.view is not None:
                    await unit_of_work.audit.record(
                        platform_audit_event(
                            context,
                            AuditAction.INITIAL_INVITATION_REVOKED,
                            result.view.first_invitation.id,
                            organization_id=organization_id,
                        )
                    )
                elif result.code is RevokeResultCode.REVOKED:
                    raise ProvisioningServiceUnavailable("La révocation n’a retourné aucune invitation.")
                await unit_of_work.commit()
        if result.code is RevokeResultCode.NOT_FOUND:
            raise ProvisioningResourceNotFound
        if result.code is RevokeResultCode.ALREADY_ACCEPTED:
            raise InvitationAlreadyAccepted
        if result.view is None:
            raise ProvisioningServiceUnavailable("La révocation n’a retourné aucune invitation.")
        return result.view


def _require_platform(has_platform_capability: bool) -> None:
    if not has_platform_capability:
        raise InsufficientCapability


async def _deliver_invitation(
    *,
    gateway: PlatformProvisioningGateway,
    delivery: InvitationDelivery,
    public_app_url: str,
    clock: Clock,
    context: ActorContext,
    view: ProvisioningView,
    delivery_attempt_id: UUID,
    raw_token: str,
    audited_unit_of_work_factory: PlatformAuditedUnitOfWorkFactory | None = None,
) -> ProvisioningView:
    invitation = view.first_invitation
    sent = True
    failure_code = None
    try:
        await delivery.send(
            InvitationMessage(
                recipient_email=invitation.recipient_email,
                organization_name=view.organization.name,
                role=invitation.role,
                expires_at=invitation.expires_at,
                invitation_link=f"{public_app_url}/accept-invitation#token={raw_token}",
            )
        )
    except InvitationDeliveryFailed:
        sent = False
        failure_code = "delivery_failed"
    try:
        if audited_unit_of_work_factory is None:
            await gateway.finalize_delivery(
                context=context,
                invitation_id=invitation.id,
                delivery_attempt_id=delivery_attempt_id,
                sent=sent,
                failure_code=failure_code,
                now=clock.now(),
            )
        else:
            async with audited_unit_of_work_factory(context) as unit_of_work:
                finalized = await unit_of_work.mutations.finalize_delivery(
                    invitation_id=invitation.id,
                    delivery_attempt_id=delivery_attempt_id,
                    sent=sent,
                    failure_code=failure_code,
                    now=clock.now(),
                )
                if finalized.transitioned:
                    await unit_of_work.audit.record(
                        platform_audit_event(
                            context,
                            AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED,
                            invitation.id,
                            {
                                "delivery_status": finalized.delivery_status.value,
                                "delivery_kind": finalized.delivery_kind,
                                "delivery_attempt_id": delivery_attempt_id,
                            },
                            organization_id=view.organization.id,
                        )
                    )
                await unit_of_work.commit()
    except ProvisioningServiceUnavailable as error:
        raise ProvisioningOutcomeUnknown from error
    delivery_status = InvitationDeliveryStatus.SENT if sent else InvitationDeliveryStatus.FAILED
    return replace(view, first_invitation=replace(invitation, delivery_status=delivery_status))


def _encode_cursor(created_at: datetime, organization_id: UUID) -> str:
    raw = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(organization_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None:
        return None, None
    if not 1 <= len(cursor) <= 512:
        raise ValueError("Le curseur est invalide.")
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(f"{cursor}{padding}"))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        organization_id = UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Le curseur est invalide.") from error
    if created_at.tzinfo is None:
        raise ValueError("Le curseur est invalide.")
    return created_at, organization_id
