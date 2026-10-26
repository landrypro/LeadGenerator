from __future__ import annotations

import json

import httpx
import pytest

from backend.app.cli import provision_stripe_sandbox_catalog as cli
from backend.app.config import Settings


def sandbox_settings() -> Settings:
    return Settings(
        app_env="development",
        billing_provider_mode="stripe_sandbox",
        billing_stripe_test_secret_key="sk_test_local",
        billing_stripe_webhook_secret="whsec_local",
        billing_stripe_price_cad_monthly="price_cad",
        billing_stripe_price_usd_monthly="price_usd",
        billing_stripe_price_eur_monthly="price_eur",
        billing_stripe_price_xaf_monthly="price_xaf",
        cors_allowed_origins=("http://localhost:5173",),
    )


async def test_catalog_uses_two_authenticated_actors_and_raw_xaf_minor_amount(monkeypatch) -> None:
    async def prices(_settings):
        return {"CAD": 2500, "USD": 2000, "EUR": 2300, "XAF": 1234}

    monkeypatch.setattr(cli, "_stripe_prices", prices)
    calls: list[tuple[str, str, dict]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if request.url.path == "/api/auth/login":
            approver = payload["email"] == cli.DEFAULT_APPROVER_EMAIL
            return httpx.Response(
                200,
                json={
                    "user": {"id": "approver" if approver else "creator", "platform_role": "platform_admin"},
                    "capabilities": ["platform:catalog:manage"],
                    "csrf_token": "approver-csrf" if approver else "creator-csrf",
                },
            )
        calls.append((request.url.path, request.headers["x-csrf-token"], payload))
        if request.url.path == "/api/platform/catalog/plans":
            return httpx.Response(200, json={"id": "plan-test"})
        if request.url.path == "/api/platform/catalog/plan-versions":
            return httpx.Response(200, json={"id": f"version-{payload['currency']}"})
        return httpx.Response(200, json={"state": "published"})

    transport = httpx.MockTransport(respond)
    async_client = httpx.AsyncClient

    def client_factory(*, base_url, headers, timeout):
        return async_client(base_url=base_url, headers=headers, timeout=timeout, transport=transport)

    monkeypatch.setattr(cli.httpx, "AsyncClient", client_factory)

    await cli.provision(
        sandbox_settings(),
        creator_email="creator@example.test",
        creator_password="creator-secret",
        approver_password="approver-secret",
    )

    versions = [body for path, csrf, body in calls if path.endswith("/plan-versions") and csrf == "creator-csrf"]
    publishes = [(path, csrf) for path, csrf, _body in calls if path.endswith("/publish")]
    assert len(versions) == len(publishes) == 4
    assert [item["currency"] for item in versions] == list(cli.CURRENCIES)
    assert versions[-1]["amount_excluding_tax_minor"] == 1234
    assert all(len(item["entitlements"]) == 8 for item in versions)
    assert all(csrf == "approver-csrf" for _path, csrf in publishes)


async def test_catalog_rejects_non_test_stripe_price_before_writing(monkeypatch) -> None:
    settings = sandbox_settings()

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _path, *, headers):
            assert headers["Authorization"].startswith("Bearer sk_test_")
            return httpx.Response(
                200,
                json={
                    "object": "price",
                    "id": "price_cad",
                    "livemode": True,
                    "active": True,
                    "currency": "cad",
                    "unit_amount": 2500,
                    "recurring": {"interval": "month", "interval_count": 1},
                },
            )

    monkeypatch.setattr(cli.httpx, "AsyncClient", lambda **_kwargs: Client())

    with pytest.raises(RuntimeError, match="CAD"):
        await cli._stripe_prices(settings)


async def test_catalog_reads_stripe_amounts_without_xaf_conversion(monkeypatch) -> None:
    amounts = {"cad": 2500, "usd": 2000, "eur": 2300, "xaf": 1234}

    def respond(request: httpx.Request) -> httpx.Response:
        currency = request.url.path.rsplit("_", 1)[-1]
        assert request.headers["Stripe-Version"] == cli.STRIPE_API_VERSION
        return httpx.Response(
            200,
            json={
                "object": "price",
                "id": f"price_{currency}",
                "livemode": False,
                "active": True,
                "currency": currency,
                "unit_amount": amounts[currency],
                "recurring": {"interval": "month", "interval_count": 1},
            },
        )

    transport = httpx.MockTransport(respond)
    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        cli.httpx,
        "AsyncClient",
        lambda **kwargs: async_client(**kwargs, transport=transport),
    )

    assert await cli._stripe_prices(sandbox_settings()) == {
        "CAD": 2500,
        "USD": 2000,
        "EUR": 2300,
        "XAF": 1234,
    }
