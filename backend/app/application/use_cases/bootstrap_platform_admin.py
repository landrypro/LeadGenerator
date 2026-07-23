from __future__ import annotations

from ...domain.identity import UserIdentity, normalize_email, validate_new_password
from ..errors import PlatformAdministratorAlreadyExists
from ..ports import Clock, IdentityUnitOfWorkFactory, PasswordHasher


class BootstrapPlatformAdministratorUseCase:
    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._clock = clock

    async def execute(self, *, email: str, display_name: str, password: str) -> UserIdentity:
        normalized_email = normalize_email(email)
        cleaned_display_name = " ".join(display_name.split())
        if not 1 <= len(cleaned_display_name) <= 120:
            raise ValueError("Le nom d’affichage doit contenir entre 1 et 120 caractères.")
        validate_new_password(password)
        password_hash = await self._password_hasher.hash(password)

        async with self._unit_of_work_factory() as unit_of_work:
            if await unit_of_work.identities.platform_administrator_exists():
                raise PlatformAdministratorAlreadyExists
            user = await unit_of_work.identities.create_platform_administrator(
                email=normalized_email.display,
                email_normalized=normalized_email.normalized,
                display_name=cleaned_display_name,
                password_hash=password_hash,
                occurred_at=self._clock.now(),
            )
            await unit_of_work.commit()
        return user
