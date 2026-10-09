from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.application.ports.billing import (
    BillingCheckoutCommand,
    BillingPortalCommand,
    BillingRefundCommand,
    BillingReturnTarget,
)
from backend.app.domain.billing import BillingPeriod, SubscriptionState
from backend.app.domain.catalog import CurrencyCode


def test_billing_commands_accept_only_a_server_selected_provider_reference() -> None:
    checkout = BillingCheckoutCommand(
        organization_id=uuid4(),
        plan_version_id=uuid4(),
        currency=CurrencyCode.CAD,
        provider_price_reference="price_sandbox_opaque",
        return_target=BillingReturnTarget.SUBSCRIPTION,
    )

    assert checkout.currency is CurrencyCode.CAD
    assert checkout.return_target is BillingReturnTarget.SUBSCRIPTION
    with pytest.raises(ValueError):
        BillingCheckoutCommand(
            organization_id=uuid4(),
            plan_version_id=uuid4(),
            currency=CurrencyCode.CAD,
            provider_price_reference=" ",
            return_target=BillingReturnTarget.SUBSCRIPTION,
        )


def test_billing_ports_do_not_accept_missing_provider_references() -> None:
    with pytest.raises(ValueError):
        BillingPortalCommand(uuid4(), "", BillingReturnTarget.SUBSCRIPTION)
    with pytest.raises(ValueError):
        BillingRefundCommand(uuid4(), "")


def test_billing_period_is_available_to_port_contracts_without_a_database() -> None:
    now = datetime(2026, 10, 9, 12, tzinfo=UTC)
    period = BillingPeriod(now, now + timedelta(days=30))

    assert period.starts_at == now
    assert SubscriptionState.PENDING_CHECKOUT.value == "pending_checkout"
