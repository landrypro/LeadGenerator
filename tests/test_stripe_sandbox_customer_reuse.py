"""Checkout preparation reuses the Stripe customer recorded for the tenant."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.application.errors import BillingOperationError
from backend.app.application.tenancy import TenantContext
from backend.app.domain.billing import BillingErrorCode
from backend.app.infrastructure.postgres.billing_commands import SqlAlchemyBillingCommandRepository


class _Session:
    def __init__(self, reference: str | None) -> None:
        self.reference = reference
        self.queries: list[str] = []

    async def scalar(self, statement):
        self.queries.append(str(statement))
        return self.reference


class _Unit:
    def __init__(self, session: _Session) -> None:
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_checkout_preparation_uses_existing_stripe_customer(monkeypatch) -> None:
    tenant = TenantContext(uuid4(), uuid4(), "reuse-stripe-customer")
    session = _Session("cus_test_existing")
    repository = SqlAlchemyBillingCommandRepository(
        lambda _context: _Unit(session), stripe_price_references={"XAF": "price_test_contract"}
    )
    plan_version_id = uuid4()
    command_id = uuid4()

    async def prepared(*_args, **_kwargs):
        return {
            "code": "reserved",
            "command_id": str(command_id),
            "status": "reserved",
            "plan_version_id": str(plan_version_id),
            "currency": "XAF",
            "provider_price_reference": "sim_price_unused",
            "amount_minor": 5000,
            "billing_cycle": "monthly",
        }

    monkeypatch.setattr(repository, "_json_call", prepared)
    result = await repository.prepare_checkout(
        context=tenant,
        command_id=command_id,
        plan_version_id=plan_version_id,
        idempotency_key_digest="a" * 64,
        request_fingerprint="b" * 64,
        now=object(),
    )

    assert result.command.provider_customer_reference == "cus_test_existing"
    assert result.command.provider_price_reference == "price_test_contract"
    assert session.queries == ["SELECT app_private.tenant_stripe_customer_reference()"]


@pytest.mark.asyncio
async def test_checkout_preparation_rejects_invalid_recorded_customer(monkeypatch) -> None:
    tenant = TenantContext(uuid4(), uuid4(), "invalid-stripe-customer")
    repository = SqlAlchemyBillingCommandRepository(
        lambda _context: _Unit(_Session("wrong_customer")), stripe_price_references={"XAF": "price_test_contract"}
    )

    async def prepared(*_args, **_kwargs):
        return {
            "code": "reserved",
            "command_id": str(uuid4()),
            "status": "reserved",
            "plan_version_id": str(uuid4()),
            "currency": "XAF",
            "provider_price_reference": "sim_price_unused",
            "amount_minor": 5000,
            "billing_cycle": "monthly",
        }

    monkeypatch.setattr(repository, "_json_call", prepared)
    with pytest.raises(BillingOperationError) as error:
        await repository.prepare_checkout(
            context=tenant,
            command_id=uuid4(),
            plan_version_id=uuid4(),
            idempotency_key_digest="a" * 64,
            request_fingerprint="b" * 64,
            now=object(),
        )
    assert error.value.code is BillingErrorCode.STATE_UNKNOWN
