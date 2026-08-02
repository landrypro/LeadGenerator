from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from ...domain.identity import UserIdentity


class IdentityRepository(Protocol):
    async def get_by_normalized_email(self, email_normalized: str) -> UserIdentity | None: ...

    async def get_by_id(self, user_id: UUID) -> UserIdentity | None: ...

    async def record_successful_login(
        self,
        user_id: UUID,
        occurred_at: datetime,
        replacement_password_hash: str | None,
    ) -> None: ...

    async def platform_administrator_exists(self) -> bool: ...

    async def create_platform_administrator(
        self,
        *,
        email: str,
        email_normalized: str,
        display_name: str,
        password_hash: str,
        occurred_at: datetime,
    ) -> UserIdentity: ...

    async def replace_platform_administrator_password(
        self,
        *,
        user_id: UUID,
        expected_version: int,
        password_hash: str,
        occurred_at: datetime,
    ) -> bool: ...


class IdentityUnitOfWork(Protocol):
    @property
    def identities(self) -> IdentityRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class IdentityUnitOfWorkFactory(Protocol):
    def __call__(self) -> IdentityUnitOfWork: ...
