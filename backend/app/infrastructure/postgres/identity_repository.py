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
from .models import UserModel


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

    async def replace_platform_administrator_password(
        self,
        *,
        user_id: UUID,
        expected_version: int,
        password_hash: str,
        occurred_at: datetime,
    ) -> bool:
        updated_user_id = await self._session.scalar(
            update(UserModel)
            .where(
                UserModel.id == user_id,
                UserModel.platform_role == PlatformRole.PLATFORM_ADMIN.value,
                UserModel.version == expected_version,
            )
            .values(
                password_hash=password_hash,
                updated_at=occurred_at,
                version=UserModel.version + 1,
            )
            .returning(UserModel.id)
        )
        return updated_user_id is not None

    async def _to_identity(self, model: UserModel | None) -> UserIdentity | None:
        if model is None:
            return None
        await self._session.execute(
            text("SELECT set_config('app.actor_id', :actor_id, true)"),
            {"actor_id": str(model.id)},
        )
        membership_rows = (
            await self._session.execute(text("SELECT * FROM app_private.identity_memberships()"))
        ).mappings()
        memberships = tuple(
            MembershipIdentity(
                id=row["membership_id"],
                organization_id=row["organization_id"],
                organization_name=row["organization_name"],
                role=MembershipRole(row["membership_role"]),
                status=MembershipStatus(row["membership_status"]),
                organization_status=OrganizationStatus(row["organization_status"]),
                created_at=row["membership_created_at"],
            )
            for row in membership_rows
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
