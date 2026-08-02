from __future__ import annotations

import asyncio
import getpass
import os

from ..application.errors import IdentityConcurrentUpdate, PlatformAdministratorNotFound
from ..application.use_cases import ResetPlatformAdministratorPasswordUseCase
from ..config import POSTGRESQL_ASYNC_PREFIX, Settings
from ..domain.identity import InvalidEmail, InvalidPassword
from ..infrastructure.clock import SystemClock
from ..infrastructure.postgres import PostgresDatabase
from ..infrastructure.security import Argon2PasswordHasher

CONFIRMATION_VALUE = "RESET_PLATFORM_ADMIN_PASSWORD"


async def run() -> int:
    if os.environ.get("ADMIN_PASSWORD_RESET_CONFIRM") != CONFIRMATION_VALUE:
        print(f"Réinitialisation refusée : définir ADMIN_PASSWORD_RESET_CONFIRM={CONFIRMATION_VALUE}.")
        return 2

    database_url = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not database_url.startswith(POSTGRESQL_ASYNC_PREFIX):
        print("Réinitialisation refusée : MIGRATION_DATABASE_URL PostgreSQL est obligatoire.")
        return 2

    email = os.environ.get("ADMIN_PASSWORD_RESET_EMAIL", "").strip()
    if not email:
        print("Réinitialisation refusée : ADMIN_PASSWORD_RESET_EMAIL est obligatoire.")
        return 2

    try:
        password = getpass.getpass("Nouveau mot de passe (12 à 128 caractères) : ")
        confirmation = getpass.getpass("Confirmer le nouveau mot de passe : ")
    except (EOFError, KeyboardInterrupt):
        print("\nRéinitialisation annulée.")
        return 2
    if password != confirmation:
        password = ""
        confirmation = ""
        print("Réinitialisation refusée : les mots de passe diffèrent.")
        return 2

    settings = Settings.from_env()
    database = PostgresDatabase(
        database_url,
        connect_timeout_seconds=settings.dependency_connect_timeout_seconds,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
        statement_timeout_ms=settings.database_statement_timeout_ms,
    )
    use_case = ResetPlatformAdministratorPasswordUseCase(
        database.identity_unit_of_work,
        Argon2PasswordHasher(),
        SystemClock(),
    )
    try:
        user_id = await use_case.execute(email=email, password=password)
    except (InvalidEmail, InvalidPassword) as error:
        print(f"Réinitialisation refusée : {error}")
        return 2
    except PlatformAdministratorNotFound:
        print("Réinitialisation refusée : aucun administrateur de plateforme ne correspond à ce courriel.")
        return 1
    except IdentityConcurrentUpdate:
        print("Réinitialisation refusée : le compte a changé simultanément ; recommencez.")
        return 1
    finally:
        password = ""
        confirmation = ""
        await database.close()

    print(f"Mot de passe réinitialisé pour l’identifiant interne {user_id} ; anciennes sessions invalidées.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
