from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...application.errors import OrganizationAdministrationUnavailable
from ...application.ports.organization import (
    CreateMemberInvitationGatewayResult,
    CreateMemberInvitationResultCode,
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
from ...application.tenancy import ActorContext, TenantContext
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
from .database import PostgresDatabase


class SqlAlchemyOrganizationAdministrationGateway:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    async def get_organization(self, *, context: TenantContext) -> OrganizationView | None:
        try:
            async with self._database.tenant_unit_of_work(context) as unit_of_work:
                row = (
                    (
                        await unit_of_work.session.execute(
                            text(
                                """
                            SELECT id, name, locale, timezone, status, version, created_at, updated_at
                            FROM public.organizations
                            WHERE id = :organization_id AND status = 'active'
                            """
                            ),
                            {"organization_id": context.organization_id},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        return _organization_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def update_organization(
        self,
        *,
        context: TenantContext,
        command: ValidatedUpdateOrganization,
        now: datetime,
    ) -> UpdateOrganizationGatewayResult:
        try:
            async with self._database.tenant_unit_of_work(context) as unit_of_work:
                raw = await unit_of_work.session.scalar(
                    text(
                        """
                        SELECT app_private.tenant_update_organization(
                            :name, :locale, :timezone, :version, :now
                        )
                        """
                    ),
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
                            await unit_of_work.session.execute(
                                text(
                                    """
                                SELECT id, name, locale, timezone, status, version, created_at, updated_at
                                FROM public.organizations WHERE id = :organization_id
                                """
                                ),
                                {"organization_id": context.organization_id},
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        return UpdateOrganizationGatewayResult(
            code=code,
            organization=(_organization_from_row(cast(Mapping[str, object], row)) if row is not None else None),
            current_version=_optional_int(payload.get("current_version")),
        )

    async def list_members(
        self,
        *,
        context: TenantContext,
        after_created_at: datetime | None,
        after_id: UUID | None,
        limit: int,
    ) -> tuple[MemberView, ...]:
        try:
            async with self._database.tenant_unit_of_work(context) as unit_of_work:
                rows = (
                    await unit_of_work.session.execute(
                        text(
                            """
                            SELECT membership.id AS membership_id, membership.user_id,
                                   candidate.email, candidate.display_name,
                                   membership.role, membership.status, membership.version,
                                   membership.created_at, membership.updated_at
                            FROM public.memberships AS membership
                            JOIN public.users AS candidate ON candidate.id = membership.user_id
                            WHERE membership.organization_id = :organization_id
                              AND (
                                  CAST(:after_created_at AS timestamp with time zone) IS NULL
                                  OR (membership.created_at, membership.id) >
                                     (CAST(:after_created_at AS timestamp with time zone), CAST(:after_id AS uuid))
                              )
                            ORDER BY membership.created_at, membership.id
                            LIMIT :limit
                            """
                        ),
                        {
                            "organization_id": context.organization_id,
                            "after_created_at": after_created_at,
                            "after_id": after_id,
                            "limit": limit,
                        },
                    )
                ).mappings()
                return tuple(_member_from_row(cast(Mapping[str, object], row)) for row in rows)
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error

    async def update_membership(
        self,
        *,
        context: TenantContext,
        membership_id: UUID,
        command: UpdateMembershipCommand,
        now: datetime,
    ) -> UpdateMembershipGatewayResult:
        role, status = membership_values(command.role, command.status)
        try:
            async with self._database.tenant_unit_of_work(context) as unit_of_work:
                raw = await unit_of_work.session.scalar(
                    text(
                        """
                        SELECT app_private.tenant_update_membership(
                            :membership_id, :role, :status, :version, :now
                        )
                        """
                    ),
                    {
                        "membership_id": membership_id,
                        "role": role,
                        "status": status,
                        "version": command.version,
                        "now": now,
                    },
                )
                payload = _json_object(raw)
                code = _enum_code(UpdateMembershipResultCode, payload)
                row = None
                if code in {UpdateMembershipResultCode.UPDATED, UpdateMembershipResultCode.UNCHANGED}:
                    row = (
                        (
                            await unit_of_work.session.execute(
                                text(
                                    """
                                SELECT membership.id AS membership_id, membership.user_id,
                                       candidate.email, candidate.display_name,
                                       membership.role, membership.status, membership.version,
                                       membership.created_at, membership.updated_at
                                FROM public.memberships AS membership
                                JOIN public.users AS candidate ON candidate.id = membership.user_id
                                WHERE membership.id = :membership_id
                                """
                                ),
                                {"membership_id": membership_id},
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        return UpdateMembershipGatewayResult(
            code=code,
            member=_member_from_row(cast(Mapping[str, object], row)) if row is not None else None,
            user_version=_optional_int(payload.get("user_version")),
            current_version=_optional_int(payload.get("current_version")),
        )

    async def list_invitations(
        self,
        *,
        context: TenantContext,
        after_created_at: datetime | None,
        after_id: UUID | None,
        limit: int,
        now: datetime,
    ) -> tuple[MemberInvitationView, ...]:
        try:
            async with self._database.tenant_unit_of_work(context) as unit_of_work:
                rows = (
                    await unit_of_work.session.execute(
                        text(
                            """
                            SELECT id AS invitation_id, email AS recipient_email,
                                   role AS invitation_role,
                                   CASE WHEN expires_at <= :now THEN 'expired' ELSE 'active' END AS invitation_state,
                                   delivery_status AS invitation_delivery_status,
                                   expires_at AS invitation_expires_at,
                                   created_at AS invitation_created_at
                            FROM public.user_invitations
                            WHERE organization_id = :organization_id
                              AND invitation_kind = 'member'
                              AND accepted_at IS NULL AND revoked_at IS NULL
                              AND (
                                  CAST(:after_created_at AS timestamp with time zone) IS NULL
                                  OR (created_at, id) >
                                     (CAST(:after_created_at AS timestamp with time zone), CAST(:after_id AS uuid))
                              )
                            ORDER BY created_at, id
                            LIMIT :limit
                            """
                        ),
                        {
                            "organization_id": context.organization_id,
                            "after_created_at": after_created_at,
                            "after_id": after_id,
                            "limit": limit,
                            "now": now,
                        },
                    )
                ).mappings()
                return tuple(_invitation_from_mapping(cast(Mapping[str, object], row), replayed=False) for row in rows)
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error

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
    ) -> CreateMemberInvitationGatewayResult:
        payload = await self._tenant_json_function(
            context,
            """
            SELECT app_private.tenant_create_member_invitation(
                :invitation_id, :delivery_attempt_id, :email, :email_normalized, :role,
                :request_id, :token_hash, :expires_at, :now
            )
            """,
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
        )

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
    ) -> MemberInvitationMutationGatewayResult:
        payload = await self._tenant_json_function(
            context,
            """
            SELECT app_private.tenant_resend_member_invitation(
                :invitation_id, :replacement_invitation_id, :delivery_attempt_id,
                :request_id, :token_hash, :expires_at, :now,
                :cooldown_seconds, :window_seconds, :max_per_window
            )
            """,
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

    async def revoke_invitation(
        self,
        *,
        context: TenantContext,
        invitation_id: UUID,
        now: datetime,
    ) -> MemberInvitationMutationGatewayResult:
        payload = await self._tenant_json_function(
            context,
            "SELECT app_private.tenant_revoke_member_invitation(:invitation_id, :now)",
            {"invitation_id": invitation_id, "now": now},
        )
        return _mutation_result(payload)

    async def finalize_delivery(
        self,
        *,
        context: TenantContext,
        invitation_id: UUID,
        delivery_attempt_id: UUID,
        sent: bool,
        failure_code: str | None,
        now: datetime,
    ) -> None:
        try:
            async with self._database.tenant_unit_of_work(context) as unit_of_work:
                finalized = await unit_of_work.session.scalar(
                    text(
                        """
                        SELECT app_private.tenant_finalize_member_invitation_delivery(
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
                    raise OrganizationAdministrationUnavailable("La livraison n’a pas pu être finalisée.")
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error

    async def switch_organization(
        self,
        *,
        context: ActorContext,
        membership_id: UUID,
        now: datetime,
    ) -> SwitchOrganizationGatewayResult:
        try:
            async with self._database.actor_unit_of_work(context) as unit_of_work:
                raw = await unit_of_work.session.scalar(
                    text("SELECT app_private.switch_active_organization(:membership_id, :now)"),
                    {"membership_id": membership_id, "now": now},
                )
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        payload = _json_object(raw)
        return SwitchOrganizationGatewayResult(
            code=_enum_code(SwitchOrganizationResultCode, payload),
            organization_id=_optional_uuid(payload.get("organization_id")),
            user_version=_optional_int(payload.get("user_version")),
        )

    async def _tenant_json_function(
        self,
        context: TenantContext,
        statement: str,
        parameters: Mapping[str, object],
    ) -> dict[str, Any]:
        try:
            async with self._database.tenant_unit_of_work(context) as unit_of_work:
                raw = await unit_of_work.session.scalar(text(statement), parameters)
                await unit_of_work.commit()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        return _json_object(raw)


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
    return _invitation_from_mapping(cast(Mapping[str, object], raw), replayed=replayed)


def _invitation_from_mapping(row: Mapping[str, object], *, replayed: bool) -> MemberInvitationView:
    try:
        return MemberInvitationView(
            id=UUID(str(row["invitation_id"])),
            recipient_email=str(row["recipient_email"]),
            role=MembershipRole(str(row["invitation_role"])),
            state=InvitationState(str(row["invitation_state"])),
            delivery_status=InvitationDeliveryStatus(str(row["invitation_delivery_status"])),
            expires_at=_datetime(row["invitation_expires_at"]),
            created_at=_datetime(row["invitation_created_at"]),
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
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))


def _optional_int(value: object) -> int | None:
    return None if value is None else int(cast(int, value))
