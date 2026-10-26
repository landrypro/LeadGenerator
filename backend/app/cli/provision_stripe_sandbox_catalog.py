"""Provision a fictitious catalog through the normal two-actor API workflow."""

from __future__ import annotations

import asyncio
import getpass
import os
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx

from ..config import Settings
from ..infrastructure.billing.stripe_contract import STRIPE_API_VERSION

CONFIRMATION_VALUE = "PROVISION_STRIPE_SANDBOX_CATALOG"
DEFAULT_APPROVER_EMAIL = "approbateur-stripe@example.test"
API_ORIGIN = "http://api:8000"
EFFECTIVE_FROM = "2026-01-01T00:00:00Z"
CURRENCIES = ("CAD", "USD", "EUR", "XAF")
ENTITLEMENTS = (
    {"key": "seats.active_members.max", "value_kind": "limit", "integer_value": 100},
    {"key": "seats.pending_invitations.max", "value_kind": "limit", "integer_value": 100},
    {"key": "prospects.active.max", "value_kind": "limit", "integer_value": 1000},
    {"key": "exports.monthly.max", "value_kind": "limit", "integer_value": 100},
    {"key": "imports.rows_per_run.max", "value_kind": "limit", "integer_value": 1000},
    {"key": "google.paid_calls.enabled", "value_kind": "switch", "boolean_value": False},
    {"key": "automation.prepare.enabled", "value_kind": "switch", "boolean_value": False},
    {"key": "automation.execute.enabled", "value_kind": "switch", "boolean_value": False},
)


def _operation_id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"marketteo-stripe-sandbox-catalog-v1:{label}"))


def _api_result(response: httpx.Response, action: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError(f"{action} : réponse API invalide (HTTP {response.status_code}).") from error
    if response.status_code >= 400:
        code = payload.get("error", {}).get("code", "unknown") if isinstance(payload, dict) else "unknown"
        raise RuntimeError(f"{action} : HTTP {response.status_code}, code {code}.")
    if not isinstance(payload, dict):
        raise RuntimeError(f"{action} : réponse API invalide.")
    return payload


async def _stripe_prices(settings: Settings) -> dict[str, int]:
    prices: dict[str, int] = {}
    async with httpx.AsyncClient(base_url="https://api.stripe.com", timeout=10.0) as client:
        for currency in CURRENCIES:
            reference = settings.stripe_sandbox_price_references[currency]
            if not reference:
                raise RuntimeError(f"Prix fictif {currency} non configuré.")
            response = await client.get(
                f"/v1/prices/{reference}",
                headers={
                    "Authorization": f"Bearer {settings.billing_stripe_test_secret_key}",
                    "Stripe-Version": STRIPE_API_VERSION,
                },
            )
            if response.status_code != 200:
                raise RuntimeError(f"Prix fictif {currency} indisponible (HTTP {response.status_code}).")
            try:
                price = response.json()
            except ValueError as error:
                raise RuntimeError(f"Réponse Stripe invalide pour le prix fictif {currency}.") from error
            if not isinstance(price, dict):
                raise RuntimeError(f"Réponse Stripe invalide pour le prix fictif {currency}.")
            amount = price.get("unit_amount")
            recurring = price.get("recurring")
            if (
                price.get("object") != "price"
                or price.get("id") != reference
                or price.get("livemode") is not False
                or price.get("active") is not True
                or price.get("currency") != currency.lower()
                or not isinstance(amount, int)
                or isinstance(amount, bool)
                or amount <= 0
                or not isinstance(recurring, dict)
                or recurring.get("interval") != "month"
                or recurring.get("interval_count") != 1
            ):
                raise RuntimeError(f"Le prix fictif {currency} n'est pas un tarif mensuel utilisable.")
            # XAF is zero-decimal in Stripe: the provider unit_amount is already the catalog minor unit.
            prices[currency] = amount
    return prices


async def _login(client: httpx.AsyncClient, email: str, password: str, label: str) -> tuple[str, str]:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    payload = _api_result(response, f"Connexion {label}")
    if payload.get("user", {}).get("platform_role") != "platform_admin":
        raise RuntimeError(f"Le compte {label} n'est pas administrateur plateforme.")
    if "platform:catalog:manage" not in payload.get("capabilities", []):
        raise RuntimeError(f"Le compte {label} ne peut pas gérer le catalogue.")
    return str(payload["user"]["id"]), str(payload["csrf_token"])


async def _mutate(
    client: httpx.AsyncClient, path: str, payload: dict[str, Any], csrf_token: str, action: str
) -> dict[str, Any]:
    response = await client.post(path, json=payload, headers={"X-CSRF-Token": csrf_token})
    return _api_result(response, action)


async def provision(settings: Settings, *, creator_email: str, creator_password: str, approver_password: str) -> None:
    prices = await _stripe_prices(settings)
    approver_email = os.environ.get("STRIPE_SANDBOX_APPROVER_EMAIL", DEFAULT_APPROVER_EMAIL)
    origin = (
        settings.public_app_url
        if settings.public_app_url in settings.cors_allowed_origins
        else settings.cors_allowed_origins[0]
    )
    async with (
        httpx.AsyncClient(base_url=API_ORIGIN, headers={"Origin": origin}, timeout=15.0) as creator,
        httpx.AsyncClient(base_url=API_ORIGIN, headers={"Origin": origin}, timeout=15.0) as approver,
    ):
        creator_id, creator_csrf = await _login(creator, creator_email, creator_password, "créateur")
        approver_id, approver_csrf = await _login(approver, approver_email, approver_password, "approbateur")
        if creator_id == approver_id:
            raise RuntimeError("Le créateur et l'approbateur doivent être deux comptes distincts.")

        plan = await _mutate(
            creator,
            "/api/platform/catalog/plans",
            {"code": "starter", "display_order": 1, "operation_id": _operation_id("plan-starter")},
            creator_csrf,
            "Création du plan fictif",
        )
        plan_id = str(plan["id"])
        for number, currency in enumerate(CURRENCIES, start=1):
            version = await _mutate(
                creator,
                "/api/platform/catalog/plan-versions",
                {
                    "plan_id": plan_id,
                    "version_number": number,
                    "currency": currency,
                    "billing_cycle": "monthly",
                    "amount_excluding_tax_minor": prices[currency],
                    "effective_from": EFFECTIVE_FROM,
                    "effective_until": None,
                    "entitlements": ENTITLEMENTS,
                    "operation_id": _operation_id(f"version-{currency}-{prices[currency]}"),
                },
                creator_csrf,
                f"Création de la version {currency}",
            )
            published = await _mutate(
                approver,
                f"/api/platform/catalog/plan-versions/{version['id']}/publish",
                {"version": 1, "operation_id": _operation_id(f"publish-{currency}-{version['id']}")},
                approver_csrf,
                f"Publication de la version {currency}",
            )
            if published.get("state") != "published":
                raise RuntimeError(f"La version {currency} n'est pas publiée.")
            print(f"Version de test {currency} publiée (montant mineur {prices[currency]}).")


async def run() -> int:
    if os.environ.get("STRIPE_SANDBOX_CATALOG_CONFIRM") != CONFIRMATION_VALUE:
        print(f"Préparation refusée : définir STRIPE_SANDBOX_CATALOG_CONFIRM={CONFIRMATION_VALUE}.")
        return 2
    try:
        settings = Settings.from_env()
    except ValueError as error:
        print(f"Préparation refusée : {error}")
        return 2
    if settings.app_env not in {"development", "test"} or settings.billing_provider_mode != "stripe_sandbox":
        print("Préparation refusée : cette commande exige l'environnement Stripe sandbox local.")
        return 2
    try:
        creator_email = (await asyncio.to_thread(input, "Courriel de l'administrateur plateforme créateur : ")).strip()
        creator_password = await asyncio.to_thread(getpass.getpass, "Mot de passe du créateur : ")
        approver_password = await asyncio.to_thread(getpass.getpass, "Mot de passe de l'approbateur de test : ")
    except (EOFError, KeyboardInterrupt):
        print("Préparation annulée.")
        return 2
    try:
        await provision(
            settings,
            creator_email=creator_email,
            creator_password=creator_password,
            approver_password=approver_password,
        )
    except (httpx.HTTPError, RuntimeError, KeyError, ValueError) as error:
        print(f"Préparation interrompue : {error}")
        return 1
    finally:
        creator_password = ""
        approver_password = ""
    print("Catalogue fictif publié. Rafraîchir /app/billing avec l'administrateur de l'organisation.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
