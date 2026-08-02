from __future__ import annotations

from uuid import UUID

from ...domain.identity import PlatformRole, normalize_email, validate_new_password
from ..errors import IdentityConcurrentUpdate, PlatformAdministratorNotFound
from ..ports import Clock, IdentityUnitOfWorkFactory, PasswordHasher


class ResetPlatformAdministratorPasswordUseCase:
    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._clock = clock

    async def execute(self, *, email: str, password: str) -> UUID:
        normalized_email = normalize_email(email)
        validate_new_password(password)
        password_hash = await self._password_hasher.hash(password)

        async with self._unit_of_work_factory() as unit_of_work:
            user = await unit_of_work.identities.get_by_normalized_email(normalized_email.normalized)
            if user is None or user.platform_role is not PlatformRole.PLATFORM_ADMIN:
                raise PlatformAdministratorNotFound
            updated = await unit_of_work.identities.replace_platform_administrator_password(
                user_id=user.id,
                expected_version=user.version,
                password_hash=password_hash,
                occurred_at=self._clock.now(),
            )
            if not updated:
                raise IdentityConcurrentUpdate
            await unit_of_work.commit()
        return user.id
