from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.errors import ProvisioningServiceUnavailable
from ...application.ports.organization import DeliveryFinalizationGatewayResult
from ...application.ports.provisioning import (
    AcceptanceGatewayResult,
    AcceptanceResultCode,
    ProvisionGatewayResult,
    ProvisionResultCode,
    ResendGatewayResult,
    ResendResultCode,
    RevokeGatewayResult,
    RevokeResultCode,
)
from ...domain.identity import MembershipRole
from ...domain.provisioning import (
    AcceptedInvitation,
    InvitationDeliveryStatus,
    InvitationKind,
    InvitationProvisioningView,
    InvitationState,
    InvitationToken,
    OrganizationProvisioningView,
    ProvisioningView,
    ValidatedProvisionOrganization,
)


class SqlAlchemyPlatformProvisioningMutations:
    """Mutations plateforme liées à une session; aucune validation transactionnelle interne."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def provision(
        self,
        *,
        command: ValidatedProvisionOrganization,
        token: InvitationToken,
        organization_id: UUID,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
    ) -> ProvisionGatewayResult:
        payload = await self._json(
            """SELECT app_private.platform_provision_organization(
                   :organization_id, :invitation_id, :delivery_attempt_id, :name, :locale,
                   :timezone, :email, :email_normalized, :creation_request_id, :fingerprint,
                   :token_hash, :expires_at, :now)""",
            {
                "organization_id": organization_id,
                "invitation_id": invitation_id,
                "delivery_attempt_id": delivery_attempt_id,
                "name": command.name,
                "locale": command.locale,
                "timezone": command.timezone,
                "email": command.first_administrator_email.display,
                "email_normalized": command.first_administrator_email.normalized,
                "creation_request_id": command.creation_request_id,
                "fingerprint": command.fingerprint,
                "token_hash": token.hash,
                "expires_at": expires_at,
                "now": now,
            },
        )
        code = _result_code(ProvisionResultCode, payload)
        return ProvisionGatewayResult(
            code=code,
            view=_view_from_json(payload.get("view"), replayed=code is ProvisionResultCode.REPLAYED),
            delivery_attempt_id=_optional_uuid(payload.get("delivery_attempt_id")),
        )

    async def prepare_resend(
        self,
        *,
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
    ) -> ResendGatewayResult:
        payload = await self._json(
            """SELECT app_private.platform_resend_initial_invitation_audited(
                   :organization_id, :invitation_id, :delivery_attempt_id, :request_id,
                   :token_hash, :expires_at, :now, :cooldown_seconds, :window_seconds,
                   :max_per_window)""",
            {
                "organization_id": organization_id,
                "invitation_id": invitation_id,
                "delivery_attempt_id": delivery_attempt_id,
                "request_id": request_id,
                "token_hash": token.hash,
                "expires_at": expires_at,
                "now": now,
                "cooldown_seconds": cooldown_seconds,
                "window_seconds": window_seconds,
                "max_per_window": max_per_window,
            },
        )
        code = _result_code(ResendResultCode, payload)
        return ResendGatewayResult(
            code=code,
            view=_view_from_json(payload.get("view"), replayed=code is ResendResultCode.REPLAYED),
            delivery_attempt_id=_optional_uuid(payload.get("delivery_attempt_id")),
            retry_after_seconds=int(payload.get("retry_after_seconds", 0)),
            revoked_invitation_id=_optional_uuid(payload.get("revoked_invitation_id")),
        )

    async def revoke_initial_invitation(self, *, organization_id: UUID, now: datetime) -> RevokeGatewayResult:
        payload = await self._json(
            "SELECT app_private.platform_revoke_initial_invitation(:organization_id, :now)",
            {"organization_id": organization_id, "now": now},
        )
        code = _result_code(RevokeResultCode, payload)
        return RevokeGatewayResult(
            code=code,
            view=_view_from_json(payload.get("view"), replayed=code is RevokeResultCode.ALREADY_REVOKED),
        )

    async def finalize_delivery(
        self,
        *,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        sent: bool,
        failure_code: str | None,
        now: datetime,
    ) -> DeliveryFinalizationGatewayResult:
        payload = await self._json(
            """SELECT app_private.platform_finalize_invitation_delivery_audited(
                   :invitation_id, :delivery_attempt_id, :sent, :failure_code, :now)""",
            {
                "invitation_id": invitation_id,
                "delivery_attempt_id": delivery_attempt_id,
                "sent": sent,
                "failure_code": failure_code,
                "now": now,
            },
        )
        return DeliveryFinalizationGatewayResult(
            transitioned=bool(payload.get("transitioned")),
            invitation_id=UUID(str(payload["invitation_id"])),
            delivery_status=InvitationDeliveryStatus(str(payload["delivery_status"])),
            delivery_kind=str(payload["delivery_kind"]),
        )

    async def _json(self, statement: str, parameters: Mapping[str, object]) -> dict[str, Any]:
        return _json_object(await self._session.scalar(text(statement), parameters))


class SqlAlchemyInvitationAcceptanceMutations:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def accept_new_account(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        membership_id: UUID,
        display_name: str,
        password_hash: str,
        now: datetime,
    ) -> AcceptanceGatewayResult:
        return _acceptance_result(
            await self._json(
                """SELECT app_private.accept_invitation_new_account_audited(
                   :token_hash, :user_id, :membership_id, :display_name, :password_hash, :now)""",
                {
                    "token_hash": token_hash,
                    "user_id": user_id,
                    "membership_id": membership_id,
                    "display_name": display_name,
                    "password_hash": password_hash,
                    "now": now,
                },
            )
        )

    async def accept_existing_account(
        self, *, token_hash: str, membership_id: UUID, now: datetime
    ) -> AcceptanceGatewayResult:
        return _acceptance_result(
            await self._json(
                "SELECT app_private.accept_invitation_existing_account_audited(:token_hash, :membership_id, :now)",
                {"token_hash": token_hash, "membership_id": membership_id, "now": now},
            )
        )

    async def _json(self, statement: str, parameters: Mapping[str, object]) -> dict[str, Any]:
        return _json_object(await self._session.scalar(text(statement), parameters))


def _acceptance_result(payload: Mapping[str, Any]) -> AcceptanceGatewayResult:
    try:
        code = AcceptanceResultCode(payload["code"])
        accepted = None
        if code is AcceptanceResultCode.ACCEPTED:
            accepted = AcceptedInvitation(
                user_id=UUID(str(payload["user_id"])),
                user_version=int(payload["user_version"]),
                organization_id=UUID(str(payload["organization_id"])),
                invitation_id=UUID(str(payload["invitation_id"])),
                invitation_kind=InvitationKind(str(payload["invitation_kind"])),
                organization_activated=bool(payload["organization_activated"]),
            )
        return AcceptanceGatewayResult(code=code, accepted=accepted)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ProvisioningServiceUnavailable("Le résultat d’acceptation PostgreSQL est invalide.") from error


def _json_object(raw: object) -> dict[str, Any]:
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ProvisioningServiceUnavailable("La fonction PostgreSQL a retourné un JSON invalide.") from error
    if not isinstance(raw, Mapping):
        raise ProvisioningServiceUnavailable("La fonction PostgreSQL a retourné un contrat invalide.")
    return {str(key): value for key, value in raw.items()}


def _view_from_json(raw: object, *, replayed: bool) -> ProvisioningView | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise ProvisioningServiceUnavailable("La vue de provisioning contient un JSON invalide.") from error
    if not isinstance(raw, Mapping):
        raise ProvisioningServiceUnavailable("La vue de provisioning est invalide.")
    row = cast(Mapping[str, object], raw)
    try:
        return ProvisioningView(
            organization=OrganizationProvisioningView(
                id=UUID(str(row["organization_id"])),
                name=str(row["organization_name"]),
                locale=str(row["organization_locale"]),
                timezone=str(row["organization_timezone"]),
                status=str(row["organization_status"]),
                version=int(cast(int, row["organization_version"])),
                created_at=_datetime(row["organization_created_at"]),
                activated_at=_optional_datetime(row["organization_activated_at"]),
            ),
            first_invitation=InvitationProvisioningView(
                id=UUID(str(row["invitation_id"])),
                recipient_email=str(row["recipient_email"]),
                role=MembershipRole(str(row["invitation_role"])),
                state=InvitationState(str(row["invitation_state"])),
                delivery_status=InvitationDeliveryStatus(str(row["invitation_delivery_status"])),
                expires_at=_datetime(row["invitation_expires_at"]),
            ),
            replayed=replayed,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ProvisioningServiceUnavailable("La vue de provisioning PostgreSQL est invalide.") from error


def _result_code[ResultCode: (ProvisionResultCode, ResendResultCode, RevokeResultCode)](
    enum_type: type[ResultCode], payload: Mapping[str, Any]
) -> ResultCode:
    try:
        return enum_type(payload["code"])
    except (KeyError, TypeError, ValueError) as error:
        raise ProvisioningServiceUnavailable("Le code de résultat PostgreSQL est invalide.") from error


def _datetime(value: object) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))
