from __future__ import annotations

import asyncio
import getpass
import os

from ..application.errors import PlatformAdministratorAlreadyExists
from ..application.use_cases import BootstrapPlatformAdministratorUseCase
from ..config import Settings
from ..domain.identity import InvalidPassword
from ..infrastructure.clock import SystemClock
from ..infrastructure.postgres import PostgresDatabase
from ..infrastructure.security import Argon2PasswordHasher

CONFIRMATION_VALUE = "CREATE_FIRST_PLATFORM_ADMIN"


async def run() -> int:
    if os.environ.get("BOOTSTRAP_PLATFORM_ADMIN_CONFIRM") != CONFIRMATION_VALUE:
        print(f"Bootstrap refusé : définir BOOTSTRAP_PLATFORM_ADMIN_CONFIRM={CONFIRMATION_VALUE}.")
        return 2

    settings = Settings.from_env()
    if not settings.database_url:
        print("Bootstrap refusé : DATABASE_URL est obligatoire.")
        return 2

    email = os.environ.get("BOOTSTRAP_PLATFORM_ADMIN_EMAIL", "").strip()
    display_name = os.environ.get("BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME", "").strip()
    if not email or not display_name:
        print("Bootstrap refusé : le courriel et le nom d’affichage sont obligatoires.")
        return 2

    password_from_environment = os.environ.pop("BOOTSTRAP_PLATFORM_ADMIN_PASSWORD", None)
    password = password_from_environment or getpass.getpass("Mot de passe initial (12 à 128 caractères) : ")
    if password_from_environment is None:
        confirmation = getpass.getpass("Confirmer le mot de passe : ")
        if password != confirmation:
            print("Bootstrap refusé : les mots de passe diffèrent.")
            return 2

    database = PostgresDatabase(
        settings.database_url,
        connect_timeout_seconds=settings.dependency_connect_timeout_seconds,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
        statement_timeout_ms=settings.database_statement_timeout_ms,
    )
    use_case = BootstrapPlatformAdministratorUseCase(
        database.identity_unit_of_work,
        Argon2PasswordHasher(),
        SystemClock(),
    )
    try:
        user = await use_case.execute(email=email, display_name=display_name, password=password)
    except InvalidPassword as error:
        print(f"Bootstrap refusé : {error}")
        return 2
    except PlatformAdministratorAlreadyExists:
        print("Bootstrap refusé : un administrateur de plateforme existe déjà.")
        return 1
    finally:
        password = ""
        await database.close()

    print(f"Administrateur de plateforme créé avec l’identifiant interne {user.id}.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
