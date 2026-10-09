from datetime import UTC, datetime, timedelta

import pytest

from backend.app.domain.billing import (
    BILLING_ERROR_HTTP_STATUS,
    BillingErrorCode,
    BillingPeriod,
    BillingProvider,
    BillingProviderMode,
    BillingValidationError,
    SubscriptionState,
    SubscriptionTransition,
    SubscriptionTransitionError,
    SubscriptionTransitionTrigger,
    next_subscription_state,
)


@pytest.mark.parametrize(
    ("current", "trigger", "expected"),
    [
        (SubscriptionState.PENDING_CHECKOUT, SubscriptionTransitionTrigger.INVOICE_PAID, SubscriptionState.ACTIVE),
        (
            SubscriptionState.PENDING_CHECKOUT,
            SubscriptionTransitionTrigger.CHECKOUT_ABANDONED,
            SubscriptionState.CANCELED,
        ),
        (SubscriptionState.ACTIVE, SubscriptionTransitionTrigger.PAYMENT_FAILED, SubscriptionState.PAST_DUE),
        (SubscriptionState.PAST_DUE, SubscriptionTransitionTrigger.INVOICE_PAID, SubscriptionState.ACTIVE),
        (
            SubscriptionState.PAST_DUE,
            SubscriptionTransitionTrigger.GRACE_PERIOD_STARTED,
            SubscriptionState.GRACE_PERIOD,
        ),
        (SubscriptionState.GRACE_PERIOD, SubscriptionTransitionTrigger.INVOICE_PAID, SubscriptionState.ACTIVE),
        (
            SubscriptionState.GRACE_PERIOD,
            SubscriptionTransitionTrigger.GRACE_PERIOD_EXPIRED,
            SubscriptionState.SUSPENDED,
        ),
        (SubscriptionState.SUSPENDED, SubscriptionTransitionTrigger.INVOICE_PAID, SubscriptionState.ACTIVE),
        (
            SubscriptionState.ACTIVE,
            SubscriptionTransitionTrigger.CANCELLATION_SCHEDULED,
            SubscriptionState.CANCELING,
        ),
        (
            SubscriptionState.PAST_DUE,
            SubscriptionTransitionTrigger.CANCELLATION_SCHEDULED,
            SubscriptionState.CANCELING,
        ),
        (
            SubscriptionState.CANCELING,
            SubscriptionTransitionTrigger.CANCELLATION_REVOKED,
            SubscriptionState.ACTIVE,
        ),
        (
            SubscriptionState.CANCELING,
            SubscriptionTransitionTrigger.CANCELLATION_CONFIRMED,
            SubscriptionState.CANCELED,
        ),
        (
            SubscriptionState.CANCELED,
            SubscriptionTransitionTrigger.NEW_CHECKOUT,
            SubscriptionState.PENDING_CHECKOUT,
        ),
    ],
)
def test_subscription_machine_accepts_only_the_approved_transitions(
    current: SubscriptionState,
    trigger: SubscriptionTransitionTrigger,
    expected: SubscriptionState,
) -> None:
    assert next_subscription_state(current, trigger) is expected
    assert SubscriptionTransition(current, trigger, expected).next_state is expected


def test_subscription_machine_refuses_a_transition_outside_the_closed_registry() -> None:
    with pytest.raises(SubscriptionTransitionError):
        next_subscription_state(SubscriptionState.ACTIVE, SubscriptionTransitionTrigger.INVOICE_PAID)
    with pytest.raises(SubscriptionTransitionError):
        SubscriptionTransition(
            SubscriptionState.PAST_DUE,
            SubscriptionTransitionTrigger.PAYMENT_FAILED,
            SubscriptionState.PAST_DUE,
        )


def test_provider_modes_exclude_real_payments_and_disabled_mode_has_no_provider() -> None:
    assert tuple(BillingProviderMode) == (
        BillingProviderMode.DISABLED,
        BillingProviderMode.SIMULATED,
        BillingProviderMode.STRIPE_SANDBOX,
    )
    assert BillingProviderMode.DISABLED.allows_provider_commands is False
    assert BillingProviderMode.DISABLED.provider is None
    assert BillingProviderMode.SIMULATED.provider is BillingProvider.SIMULATED
    assert BillingProviderMode.STRIPE_SANDBOX.provider is BillingProvider.STRIPE


def test_billing_error_registry_is_closed_and_uses_the_approved_http_statuses() -> None:
    assert set(BILLING_ERROR_HTTP_STATUS) == set(BillingErrorCode)
    assert BillingErrorCode.CAPABILITY_REQUIRED.http_status == 403
    assert BillingErrorCode.WEBHOOK_INVALID.http_status == 400
    assert BillingErrorCode.COMMAND_CONFLICT.http_status == 409
    assert BillingErrorCode.CURRENCY_UNAVAILABLE.http_status == 422
    assert BillingErrorCode.PROVIDER_DISABLED.http_status == 503


def test_billing_period_requires_bounded_timezone_aware_dates() -> None:
    now = datetime(2026, 10, 9, 12, tzinfo=UTC)
    assert BillingPeriod(now, now + timedelta(days=30)).ends_at == now + timedelta(days=30)
    with pytest.raises(BillingValidationError):
        BillingPeriod(now, now)
    with pytest.raises(BillingValidationError):
        BillingPeriod(now.replace(tzinfo=None), now + timedelta(days=30))
