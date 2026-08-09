from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.errors import OrganizationAdministrationUnavailable
from ...application.ports.organization import (
    CreateMemberInvitationGatewayResult,
    CreateMemberInvitationResultCode,
    DeliveryFinalizationGatewayResult,
    MemberInvitationMutationGatewayResult,
    MemberInvitationMutationResultCode,
    SwitchOrganizationGatewayResult,
    SwitchOrganizationResultCode,
    UpdateMembershipGatewayResult,
    UpdateMembershipResultCode,
    UpdateOrganizationGatewayResult,
    UpdateOrganizationResultCode,
    membership_values,
)
from ...domain.identity import MembershipRole, MembershipStatus
from ...domain.organization import (
    MemberInvitationView,
    MemberView,
    OrganizationView,
    UpdateMembershipCommand,
    ValidatedCreateMemberInvitation,
    ValidatedUpdateOrganization,
)
from ...domain.provisioning import InvitationDeliveryStatus, InvitationState, InvitationToken


class SqlAlchemyTenantOrganizationMutations:
    """Mutations locataires liées à une session; cette classe ne valide jamais la transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def update_organization(
        self, *, command: ValidatedUpdateOrganization, now: datetime
    ) -> UpdateOrganizationGatewayResult:
        raw = await self._session.scalar(
            text("SELECT app_private.tenant_update_organization_audited(:name, :locale, :timezone, :version, :now)"),
            {
                "name": command.name,
                "locale": command.locale,
                "timezone": command.timezone,
                "version": command.version,
                "now": now,
            },
        )
        payload = _json_object(raw)
        code = _enum_code(UpdateOrganizationResultCode, payload)
        row = None
        if code in {UpdateOrganizationResultCode.UPDATED, UpdateOrganizationResultCode.UNCHANGED}:
            row = (
                (
                    await self._session.execute(
                        text(
                            """SELECT id, name, locale, timezone, status, version, created_at, updated_at
                   FROM public.organizations WHERE id = app_private.current_organization_id()"""
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
        return UpdateOrganizationGatewayResult(
            code=code,
            organization=_organization_from_row(cast(Mapping[str, object], row)) if row is not None else None,
            current_version=_optional_int(payload.get("current_version")),
            changed_fields=tuple(str(value) for value in payload.get("changed_fields", ())),
        )

    async def update_membership(
        self, *, membership_id: UUID, command: UpdateMembershipCommand, now: datetime
    ) -> UpdateMembershipGatewayResult:
        role, status = membership_values(command.role, command.status)
        raw = await self._session.scalar(
            text("SELECT app_private.tenant_update_membership_audited(:membership_id, :role, :status, :version, :now)"),
            {"membership_id": membership_id, "role": role, "status": status, "version": command.version, "now": now},
        )
        payload = _json_object(raw)
        code = _enum_code(UpdateMembershipResultCode, payload)
        row = None
        if code in {UpdateMembershipResultCode.UPDATED, UpdateMembershipResultCode.UNCHANGED}:
            row = (
                (
                    await self._session.execute(
                        text(
                            """SELECT membership.id AS membership_id, membership.user_id,
                          candidate.email, candidate.display_name, membership.role, membership.status,
                          membership.version, membership.created_at, membership.updated_at
                   FROM public.memberships AS membership
                   JOIN public.users AS candidate ON candidate.id = membership.user_id
                   WHERE membership.id = :membership_id"""
                        ),
                        {"membership_id": membership_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
        return UpdateMembershipGatewayResult(
            code=code,
            member=_member_from_row(cast(Mapping[str, object], row)) if row is not None else None,
            user_version=_optional_int(payload.get("user_version")),
            current_version=_optional_int(payload.get("current_version")),
            previous_role=_optional_enum(payload.get("previous_role"), type(command.role)) if command.role else None,
            previous_status=_optional_enum(payload.get("previous_status"), type(command.status))
            if command.status
            else None,
        )

    async def create_invitation(
        self,
        *,
        command: ValidatedCreateMemberInvitation,
        token: InvitationToken,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        expires_at: datetime,
        now: datetime,
    ) -> CreateMemberInvitationGatewayResult:
        payload = await self._json(
            """SELECT app_private.tenant_create_member_invitation_audited(
                   :invitation_id, :delivery_attempt_id, :email, :email_normalized, :role,
                   :request_id, :token_hash, :expires_at, :now)""",
            {
                "invitation_id": invitation_id,
                "delivery_attempt_id": delivery_attempt_id,
                "email": command.email.display,
                "email_normalized": command.email.normalized,
                "role": command.role.value,
                "request_id": command.invitation_request_id,
                "token_hash": token.hash,
                "expires_at": expires_at,
                "now": now,
            },
        )
        code = _enum_code(CreateMemberInvitationResultCode, payload)
        return CreateMemberInvitationGatewayResult(
            code=code,
            invitation=_invitation_from_json(
                payload.get("view"), replayed=code is CreateMemberInvitationResultCode.REPLAYED
            ),
            delivery_attempt_id=_optional_uuid(payload.get("delivery_attempt_id")),
            revoked_invitation_id=_optional_uuid(payload.get("revoked_invitation_id")),
        )

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
    ) -> MemberInvitationMutationGatewayResult:
        payload = await self._json(
            """SELECT app_private.tenant_resend_member_invitation_audited(
                   :invitation_id, :replacement_invitation_id, :delivery_attempt_id,
                   :request_id, :token_hash, :expires_at, :now,
                   :cooldown_seconds, :window_seconds, :max_per_window)""",
            {
                "invitation_id": invitation_id,
                "replacement_invitation_id": replacement_invitation_id,
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
        return _mutation_result(payload)

    async def revoke_invitation(self, *, invitation_id: UUID, now: datetime) -> MemberInvitationMutationGatewayResult:
        return _mutation_result(
            await self._json(
                "SELECT app_private.tenant_revoke_member_invitation(:invitation_id, :now)",
                {"invitation_id": invitation_id, "now": now},
            )
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
            """SELECT app_private.tenant_finalize_member_invitation_delivery_audited(
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


class SqlAlchemyActorOrganizationMutations:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def switch_organization(self, *, membership_id: UUID, now: datetime) -> SwitchOrganizationGatewayResult:
        payload = _json_object(
            await self._session.scalar(
                text("SELECT app_private.switch_active_organization_audited(:membership_id, :now)"),
                {"membership_id": membership_id, "now": now},
            )
        )
        return SwitchOrganizationGatewayResult(
            code=_enum_code(SwitchOrganizationResultCode, payload),
            organization_id=_optional_uuid(payload.get("organization_id")),
            user_version=_optional_int(payload.get("user_version")),
            previous_membership_id=_optional_uuid(payload.get("previous_membership_id")),
            new_membership_id=_optional_uuid(payload.get("new_membership_id")),
        )


def _optional_enum(value: object, enum_type: type[Any]) -> Any | None:
    return None if value is None else enum_type(str(value))


def _organization_from_row(row: Mapping[str, object]) -> OrganizationView:
    return OrganizationView(
        id=UUID(str(row["id"])),
        name=str(row["name"]),
        locale=str(row["locale"]),
        timezone=str(row["timezone"]),
        status=str(row["status"]),
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
    )


def _member_from_row(row: Mapping[str, object]) -> MemberView:
    return MemberView(
        membership_id=UUID(str(row["membership_id"])),
        user_id=UUID(str(row["user_id"])),
        email=str(row["email"]),
        display_name=str(row["display_name"]),
        role=MembershipRole(str(row["role"])),
        status=MembershipStatus(str(row["status"])),
        version=int(cast(int, row["version"])),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
    )


def _invitation_from_json(raw: object, *, replayed: bool) -> MemberInvitationView | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as error:
            raise OrganizationAdministrationUnavailable("La vue d’invitation est invalide.") from error
    if not isinstance(raw, Mapping):
        raise OrganizationAdministrationUnavailable("La vue d’invitation est invalide.")
    try:
        return MemberInvitationView(
            id=UUID(str(raw["invitation_id"])),
            recipient_email=str(raw["recipient_email"]),
            role=MembershipRole(str(raw["invitation_role"])),
            state=InvitationState(str(raw["invitation_state"])),
            delivery_status=InvitationDeliveryStatus(str(raw["invitation_delivery_status"])),
            expires_at=_datetime(raw["invitation_expires_at"]),
            created_at=_datetime(raw["invitation_created_at"]),
            replayed=replayed,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise OrganizationAdministrationUnavailable("La vue d’invitation PostgreSQL est invalide.") from error


def _mutation_result(payload: Mapping[str, Any]) -> MemberInvitationMutationGatewayResult:
    code = _enum_code(MemberInvitationMutationResultCode, payload)
    return MemberInvitationMutationGatewayResult(
        code=code,
        invitation=_invitation_from_json(
            payload.get("view"), replayed=code is MemberInvitationMutationResultCode.REPLAYED
        ),
        delivery_attempt_id=_optional_uuid(payload.get("delivery_attempt_id")),
        retry_after_seconds=int(payload.get("retry_after_seconds", 0)),
        revoked_invitation_id=_optional_uuid(payload.get("revoked_invitation_id")),
    )


def _json_object(raw: object) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as error:
            raise OrganizationAdministrationUnavailable(
                "La fonction PostgreSQL a retourné un JSON invalide."
            ) from error
    if not isinstance(raw, Mapping):
        raise OrganizationAdministrationUnavailable("La fonction PostgreSQL a retourné un contrat invalide.")
    return {str(key): value for key, value in raw.items()}


def _enum_code[ResultCode: StrEnum](enum_type: type[ResultCode], payload: Mapping[str, Any]) -> ResultCode:
    try:
        return enum_type(payload["code"])
    except (KeyError, TypeError, ValueError) as error:
        raise OrganizationAdministrationUnavailable("Le code PostgreSQL est invalide.") from error


def _datetime(value: object) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))


def _optional_int(value: object) -> int | None:
    return None if value is None else int(cast(int, value))
