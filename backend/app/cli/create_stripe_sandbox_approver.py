"""Provision one local-only platform approver for the Stripe sandbox recipe."""

from __future__ import annotations

import asyncio
import getpass
import os

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..config import POSTGRESQL_ASYNC_PREFIX, Settings
from ..domain.identity import InvalidEmail, InvalidPassword, normalize_email, validate_new_password
from ..infrastructure.clock import SystemClock
from ..infrastructure.postgres import PostgresDatabase
from ..infrastructure.security import Argon2PasswordHasher

CONFIRMATION_VALUE = "CREATE_STRIPE_SANDBOX_APPROVER"
DEFAULT_EMAIL = "approbateur-stripe@example.test"
DEFAULT_DISPLAY_NAME = "Approbateur Stripe sandbox"


async def run() -> int:
    if os.environ.get("STRIPE_SANDBOX_APPROVER_CONFIRM") != CONFIRMATION_VALUE:
        print(f"Création refusée : définir STRIPE_SANDBOX_APPROVER_CONFIRM={CONFIRMATION_VALUE}.")
        return 2

    try:
        settings = Settings.from_env()
    except ValueError as error:
        print(f"Création refusée : {error}")
        return 2
    if settings.app_env not in {"development", "test"} or settings.billing_provider_mode != "stripe_sandbox":
        print("Création refusée : cette commande exige l'environnement local Stripe sandbox.")
        return 2
    database_url = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not database_url.startswith(POSTGRESQL_ASYNC_PREFIX):
        print("Création refusée : MIGRATION_DATABASE_URL PostgreSQL est obligatoire.")
        return 2

    raw_email = os.environ.get("STRIPE_SANDBOX_APPROVER_EMAIL", DEFAULT_EMAIL)
    display_name = " ".join(os.environ.get("STRIPE_SANDBOX_APPROVER_DISPLAY_NAME", DEFAULT_DISPLAY_NAME).split())
    try:
        email = normalize_email(raw_email)
        if not email.normalized.endswith((".test", ".invalid")):
            raise InvalidEmail("Utiliser un courriel réservé aux tests (.test ou .invalid).")
        if not 1 <= len(display_name) <= 120:
            raise ValueError("Le nom d'affichage doit contenir entre 1 et 120 caractères.")
        password = getpass.getpass("Mot de passe du compte de test (12 à 128 caractères) : ")
        confirmation = getpass.getpass("Confirmer le mot de passe : ")
        if password != confirmation:
            print("Création refusée : les mots de passe diffèrent.")
            return 2
        validate_new_password(password)
    except (InvalidEmail, InvalidPassword, ValueError, EOFError, KeyboardInterrupt) as error:
        print(f"Création refusée : {error or 'saisie interrompue'}")
        return 2
    finally:
        confirmation = ""

    password_hash = await Argon2PasswordHasher().hash(password)
    password = ""
    database = PostgresDatabase(
        database_url,
        connect_timeout_seconds=settings.dependency_connect_timeout_seconds,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
        statement_timeout_ms=settings.database_statement_timeout_ms,
    )
    try:
        async with database.identity_unit_of_work() as unit:
            # Reuse the bootstrap advisory lock so concurrent provisioning stays serialized.
            await unit.identities.platform_administrator_exists()
            count = await unit.session.scalar(
                text("SELECT count(*) FROM public.users WHERE platform_role='platform_admin'")
            )
            if count != 1:
                print("Création refusée : exactement un administrateur plateforme doit déjà exister.")
                return 1
            existing = await unit.identities.get_by_normalized_email(email.normalized)
            if existing is not None:
                print("Création refusée : ce courriel est déjà utilisé.")
                return 1
            user = await unit.identities.create_platform_administrator(
                email=email.display,
                email_normalized=email.normalized,
                display_name=display_name,
                password_hash=password_hash,
                occurred_at=SystemClock().now(),
            )
            await unit.commit()
    except IntegrityError:
        print("Création refusée : le compte existe déjà ou a été créé simultanément.")
        return 1
    finally:
        password_hash = ""
        await database.close()

    print(f"Compte approbateur de test créé : {email.display} ({user.id}).")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
