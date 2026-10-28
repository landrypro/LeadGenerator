"""Sélection fermée des adaptateurs Billing P53-03."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ...application.ports.billing import BillingProviderGateway
from ...config import Settings
from ...domain.billing import BillingProviderMode
from .disabled import DisabledBillingProviderGateway
from .simulated import SimulatedBillingProviderGateway
from .stripe_client import StripeSandboxClient
from .stripe_sandbox import StripeSandboxProviderGateway


def build_billing_provider_gateway(
    settings: Settings, *, clock: Callable[[], datetime] | None = None
) -> BillingProviderGateway:
    """Construit uniquement l'adaptateur explicitement autorisé.

    Stripe sandbox n'est pas remplacé silencieusement par le simulateur : cet
    adaptateur appartient à P53-09 et doit être ajouté avec ses secrets dédiés.
    """

    mode = BillingProviderMode(settings.billing_provider_mode)
    if mode is BillingProviderMode.DISABLED:
        return DisabledBillingProviderGateway()
    if mode is BillingProviderMode.SIMULATED:
        return SimulatedBillingProviderGateway(
            webhook_secret=settings.billing_simulator_webhook_secret.encode("utf-8"),
            previous_webhook_secret=(
                settings.billing_simulator_previous_webhook_secret.encode("utf-8")
                if settings.billing_simulator_previous_webhook_secret
                else None
            ),
            clock=clock,
        )
    return StripeSandboxProviderGateway(
        client=StripeSandboxClient(test_secret_key=settings.billing_stripe_test_secret_key),
        return_origin=settings.public_app_url or "http://localhost:5173",
        portal_configuration_id=settings.billing_stripe_portal_configuration_id,
    )
