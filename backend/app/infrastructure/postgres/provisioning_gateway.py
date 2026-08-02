from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...application.errors import ProvisioningServiceUnavailable
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
from ...application.tenancy import ActorContext
from ...domain.identity import MembershipRole
from ...domain.provisioning import (
    AcceptedInvitation,
    InvitationDeliveryStatus,
    InvitationPreview,
    InvitationProvisioningView,
    InvitationState,
    InvitationToken,
    OrganizationProvisioningView,
    ProvisioningView,
    ValidatedProvisionOrganization,
)
from .database import PostgresDatabase


class SqlAlchemyProvisioningGateway:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

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
    ) -> ProvisionGatewayResult:
        parameters = {
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
        }
        payload = await self._actor_json_function(
            context,
            """
            SELECT app_private.platform_provision_organization(
                :organization_id, :invitation_id, :delivery_attempt_id, :name, :locale,
                :timezone, :email, :email_normalized, :creation_request_id, :fingerprint,
                :token_hash, :expires_at, :now
            )
            """,
            parameters,
        )
        code = _result_code(ProvisionResultCode, payload)
        return ProvisionGatewayResult(
            code=code,
            view=_view_from_json(payload.get("view"), replayed=code is ProvisionResultCode.REPLAYED),
            delivery_attempt_id=_optional_uuid(payload.get("delivery_attempt_id")),
        )

    async def list_organizations(
        self,
        *,
        context: ActorContext,
        before_created_at: datetime | None,
        before_id: UUID | None,
        limit: int,
        now: datetime,
    ) -> tuple[ProvisioningView, ...]:
        try:
            async with self._database.actor_unit_of_work(context) as unit_of_work:
                rows = (
                    await unit_of_work.session.execute(
                        text(
                            """
                            SELECT * FROM app_private.platform_list_organizations(
                                CAST(:before_created_at AS timestamp with time zone),
                                CAST(:before_id AS uuid), :limit, :now
                            )
                            """
                        ),
                        {
                            "before_created_at": before_created_at,
                            "before_id": before_id,
                            "limit": limit,
                            "now": now,
                        },
                    )
                ).mappings()
                return tuple(_view_from_row(cast(Mapping[str, object], row), replayed=False) for row in rows)
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error

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
    ) -> ResendGatewayResult:
        payload = await self._actor_json_function(
            context,
            """
            SELECT app_private.platform_resend_initial_invitation(
                :organization_id, :invitation_id, :delivery_attempt_id, :request_id,
                :token_hash, :expires_at, :now, :cooldown_seconds, :window_seconds,
                :max_per_window
            )
            """,
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
        )

    async def revoke_initial_invitation(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        now: datetime,
    ) -> RevokeGatewayResult:
        payload = await self._actor_json_function(
            context,
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
        context: ActorContext,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        sent: bool,
        failure_code: str | None,
        now: datetime,
    ) -> None:
        try:
            async with self._database.actor_unit_of_work(context) as unit_of_work:
                finalized = await unit_of_work.session.scalar(
                    text(
                        """
                        SELECT app_private.platform_finalize_invitation_delivery(
                            :invitation_id, :delivery_attempt_id, :sent, :failure_code, :now
                        )
                        """
                    ),
                    {
                        "invitation_id": invitation_id,
                        "delivery_attempt_id": delivery_attempt_id,
                        "sent": sent,
                        "failure_code": failure_code,
                        "now": now,
                    },
                )
                if finalized is not True:
                    raise ProvisioningServiceUnavailable("La tentative de livraison n’a pas pu être finalisée.")
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error

    async def preview(self, *, token_hash: str, now: datetime) -> InvitationPreview | None:
        try:
            async with self._database.unit_of_work() as unit_of_work:
                row = (
                    (
                        await unit_of_work.session.execute(
                            text("SELECT * FROM app_private.invitation_preview(:token_hash, :now)"),
                            {"token_hash": token_hash, "now": now},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error
        if row is None:
            return None
        return InvitationPreview(
            organization_name=str(row["organization_name"]),
            role=MembershipRole(row["invitation_role"]),
            expires_at=_datetime(row["invitation_expires_at"]),
            existing_account=bool(row["existing_account"]),
        )

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
        payload = await self._json_function(
            """
            SELECT app_private.accept_invitation_new_account(
                :token_hash, :user_id, :membership_id, :display_name, :password_hash, :now
            )
            """,
            {
                "token_hash": token_hash,
                "user_id": user_id,
                "membership_id": membership_id,
                "display_name": display_name,
                "password_hash": password_hash,
                "now": now,
            },
        )
        return _acceptance_result(payload)

    async def accept_existing_account(
        self,
        *,
        context: ActorContext,
        token_hash: str,
        membership_id: UUID,
        now: datetime,
    ) -> AcceptanceGatewayResult:
        payload = await self._actor_json_function(
            context,
            """
            SELECT app_private.accept_invitation_existing_account(
                :token_hash, :membership_id, :now
            )
            """,
            {"token_hash": token_hash, "membership_id": membership_id, "now": now},
        )
        return _acceptance_result(payload)

    async def _actor_json_function(
        self,
        context: ActorContext,
        statement: str,
        parameters: Mapping[str, object],
    ) -> dict[str, Any]:
        try:
            async with self._database.actor_unit_of_work(context) as unit_of_work:
                raw = await unit_of_work.session.scalar(text(statement), parameters)
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error
        return _json_object(raw)

    async def _json_function(self, statement: str, parameters: Mapping[str, object]) -> dict[str, Any]:
        try:
            async with self._database.unit_of_work() as unit_of_work:
                raw = await unit_of_work.session.scalar(text(statement), parameters)
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error
        return _json_object(raw)


def _acceptance_result(payload: Mapping[str, Any]) -> AcceptanceGatewayResult:
    try:
        code = AcceptanceResultCode(payload["code"])
        accepted = None
        if code is AcceptanceResultCode.ACCEPTED:
            accepted = AcceptedInvitation(
                user_id=UUID(str(payload["user_id"])),
                user_version=int(payload["user_version"]),
                organization_id=UUID(str(payload["organization_id"])),
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
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ProvisioningServiceUnavailable("La vue de provisioning contient un JSON invalide.") from error
    if not isinstance(raw, Mapping):
        raise ProvisioningServiceUnavailable("La vue de provisioning est invalide.")
    return _view_from_row(cast(Mapping[str, object], raw), replayed=replayed)


def _view_from_row(row: Mapping[str, object], *, replayed: bool) -> ProvisioningView:
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
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))
