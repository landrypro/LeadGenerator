from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.identity import (
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    PlatformRole,
    UserIdentity,
    UserStatus,
)
from .models import MembershipModel, OrganizationModel, UserModel


class SqlAlchemyIdentityRepository:
    _BOOTSTRAP_LOCK_ID = 0x50524F5350454354

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_normalized_email(self, email_normalized: str) -> UserIdentity | None:
        model = await self._session.scalar(select(UserModel).where(UserModel.email_normalized == email_normalized))
        return await self._to_identity(model)

    async def get_by_id(self, user_id: UUID) -> UserIdentity | None:
        model = await self._session.get(UserModel, user_id)
        return await self._to_identity(model)

    async def record_successful_login(
        self,
        user_id: UUID,
        occurred_at: datetime,
        replacement_password_hash: str | None,
    ) -> None:
        values: dict[str, object] = {
            "last_login_at": occurred_at,
            "updated_at": occurred_at,
        }
        if replacement_password_hash is not None:
            values["password_hash"] = replacement_password_hash
        await self._session.execute(update(UserModel).where(UserModel.id == user_id).values(**values))

    async def platform_administrator_exists(self) -> bool:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": self._BOOTSTRAP_LOCK_ID},
        )
        query = select(exists().where(UserModel.platform_role == PlatformRole.PLATFORM_ADMIN.value))
        return bool(await self._session.scalar(query))

    async def create_platform_administrator(
        self,
        *,
        email: str,
        email_normalized: str,
        display_name: str,
        password_hash: str,
        occurred_at: datetime,
    ) -> UserIdentity:
        model = UserModel(
            id=uuid4(),
            email=email,
            email_normalized=email_normalized,
            display_name=display_name,
            password_hash=password_hash,
            status=UserStatus.ACTIVE.value,
            platform_role=PlatformRole.PLATFORM_ADMIN.value,
            last_active_organization_id=None,
            last_login_at=None,
            created_at=occurred_at,
            updated_at=occurred_at,
            version=1,
        )
        self._session.add(model)
        await self._session.flush()
        identity = await self._to_identity(model)
        if identity is None:
            raise RuntimeError("L’administrateur créé n’a pas pu être relu.")
        return identity

    async def _to_identity(self, model: UserModel | None) -> UserIdentity | None:
        if model is None:
            return None
        membership_rows = (
            await self._session.execute(
                select(MembershipModel, OrganizationModel)
                .join(OrganizationModel, OrganizationModel.id == MembershipModel.organization_id)
                .where(MembershipModel.user_id == model.id)
                .order_by(MembershipModel.created_at, MembershipModel.id)
            )
        ).all()
        memberships = tuple(
            MembershipIdentity(
                id=membership.id,
                organization_id=organization.id,
                organization_name=organization.name,
                role=MembershipRole(membership.role),
                status=MembershipStatus(membership.status),
                organization_status=OrganizationStatus(organization.status),
                created_at=membership.created_at,
            )
            for membership, organization in membership_rows
        )
        return UserIdentity(
            id=model.id,
            email=model.email,
            display_name=model.display_name,
            password_hash=model.password_hash,
            status=UserStatus(model.status),
            platform_role=PlatformRole(model.platform_role) if model.platform_role else None,
            last_active_organization_id=model.last_active_organization_id,
            version=model.version,
            memberships=memberships,
        )
