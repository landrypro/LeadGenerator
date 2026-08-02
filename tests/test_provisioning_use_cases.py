from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.application.errors import (
    IdempotencyKeyReused,
    InvitationDeliveryFailed,
    InvitationInvalid,
    InvitationRateLimited,
    ProvisioningOutcomeUnknown,
)
from backend.app.application.ports.provisioning import (
    InvitationLimitStatus,
    ProvisionGatewayResult,
    ProvisionResultCode,
)
from backend.app.application.tenancy import ActorContext
from backend.app.application.use_cases.invitations import PreviewInvitationUseCase
from backend.app.application.use_cases.provisioning import CreateOrganizationUseCase
from backend.app.domain.identity import MembershipRole
from backend.app.domain.provisioning import (
    InvitationDeliveryStatus,
    InvitationPreview,
    InvitationProvisioningView,
    InvitationState,
    InvitationToken,
    OrganizationProvisioningView,
    ProvisioningView,
    ProvisionOrganizationCommand,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)
RAW_TOKEN = "A" * 43


class Clock:
    def now(self) -> datetime:
        return NOW


class TokenGenerator:
    def generate(self) -> InvitationToken:
        return InvitationToken(RAW_TOKEN, "f" * 64)


class Delivery:
    is_configured = True

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages = []

    async def send(self, message) -> None:
        self.messages.append(message)
        if self.fail:
            raise InvitationDeliveryFailed


class Gateway:
    def __init__(self, result: ProvisionGatewayResult, *, finalization_fails: bool = False) -> None:
        self.result = result
        self.finalization_fails = finalization_fails
        self.finalizations = []

    async def provision(self, **kwargs) -> ProvisionGatewayResult:
        self.provision_args = kwargs
        return self.result

    async def finalize_delivery(self, **kwargs) -> None:
        from backend.app.application.errors import ProvisioningServiceUnavailable

        self.finalizations.append(kwargs)
        if self.finalization_fails:
            raise ProvisioningServiceUnavailable


def view(*, replayed: bool = False) -> ProvisioningView:
    organization_id = uuid4()
    return ProvisioningView(
        OrganizationProvisioningView(
            organization_id,
            "Exemple",
            "fr-CA",
            "America/Toronto",
            "provisioning",
            1,
            NOW,
            None,
        ),
        InvitationProvisioningView(
            uuid4(),
            "admin@example.ca",
            MembershipRole.ADMIN,
            InvitationState.ACTIVE,
            InvitationDeliveryStatus.PENDING,
            NOW + timedelta(days=3),
        ),
        replayed,
    )


def command() -> ProvisionOrganizationCommand:
    return ProvisionOrganizationCommand("Exemple", "fr-CA", "America/Toronto", "admin@example.ca", uuid4())


def use_case(gateway: Gateway, delivery: Delivery) -> CreateOrganizationUseCase:
    return CreateOrganizationUseCase(
        gateway,
        TokenGenerator(),
        delivery,
        Clock(),
        public_app_url="https://crm.example",
        invitation_ttl_seconds=259_200,
    )


async def test_create_delivers_once_after_commit_and_never_exposes_the_raw_token() -> None:
    created_view = view()
    attempt_id = uuid4()
    gateway = Gateway(ProvisionGatewayResult(ProvisionResultCode.CREATED, created_view, attempt_id))
    delivery = Delivery()

    result = await use_case(gateway, delivery).execute(
        context=ActorContext(uuid4(), "request-1"),
        command=command(),
        has_platform_capability=True,
    )

    assert result.first_invitation.delivery_status is InvitationDeliveryStatus.SENT
    assert len(delivery.messages) == 1
    assert delivery.messages[0].invitation_link == f"https://crm.example/accept-invitation#token={RAW_TOKEN}"
    assert gateway.finalizations[0]["sent"] is True
    assert RAW_TOKEN not in repr(result)


async def test_idempotent_replay_never_sends_a_second_message() -> None:
    replay = view(replayed=True)
    delivery = Delivery()
    result = await use_case(Gateway(ProvisionGatewayResult(ProvisionResultCode.REPLAYED, replay)), delivery).execute(
        context=ActorContext(uuid4(), "request-2"), command=command(), has_platform_capability=True
    )

    assert result.replayed
    assert delivery.messages == []


async def test_delivery_failure_is_durable_but_finalization_failure_is_unknown() -> None:
    pending = view()
    attempt_id = uuid4()
    failed_gateway = Gateway(ProvisionGatewayResult(ProvisionResultCode.CREATED, pending, attempt_id))
    failed_result = await use_case(failed_gateway, Delivery(fail=True)).execute(
        context=ActorContext(uuid4(), "request-3"), command=command(), has_platform_capability=True
    )
    assert failed_result.first_invitation.delivery_status is InvitationDeliveryStatus.FAILED
    assert failed_gateway.finalizations[0]["failure_code"] == "delivery_failed"

    unknown_gateway = Gateway(
        ProvisionGatewayResult(ProvisionResultCode.CREATED, pending, attempt_id), finalization_fails=True
    )
    with pytest.raises(ProvisioningOutcomeUnknown):
        await use_case(unknown_gateway, Delivery()).execute(
            context=ActorContext(uuid4(), "request-4"), command=command(), has_platform_capability=True
        )


async def test_reused_idempotency_key_is_rejected_before_delivery() -> None:
    delivery = Delivery()
    with pytest.raises(IdempotencyKeyReused):
        await use_case(Gateway(ProvisionGatewayResult(ProvisionResultCode.IDEMPOTENCY_CONFLICT)), delivery).execute(
            context=ActorContext(uuid4(), "request-5"), command=command(), has_platform_capability=True
        )
    assert delivery.messages == []


class PreviewGateway:
    def __init__(self, preview: InvitationPreview | None) -> None:
        self.result = preview
        self.calls = 0

    async def preview(self, *, token_hash: str, now: datetime) -> InvitationPreview | None:
        assert len(token_hash) == 64 and now == NOW
        self.calls += 1
        return self.result


class Limiter:
    def __init__(self, blocked: bool = False) -> None:
        self.blocked = blocked

    async def consume(self, *, client_address: str, token_hash: str) -> InvitationLimitStatus:
        assert client_address == "192.0.2.1"
        assert len(token_hash) == 64
        return InvitationLimitStatus(self.blocked, 71 if self.blocked else 0)


async def test_preview_is_generic_for_malformed_or_unknown_tokens_and_fails_closed_on_limit() -> None:
    preview_gateway = PreviewGateway(None)
    use_case_preview = PreviewInvitationUseCase(preview_gateway, Limiter(), Clock())
    with pytest.raises(InvitationInvalid):
        await use_case_preview.execute(token="malformed", client_address="192.0.2.1")
    assert preview_gateway.calls == 0

    with pytest.raises(InvitationInvalid):
        await use_case_preview.execute(token=RAW_TOKEN, client_address="192.0.2.1")
    assert preview_gateway.calls == 1

    with pytest.raises(InvitationRateLimited) as error:
        await PreviewInvitationUseCase(preview_gateway, Limiter(blocked=True), Clock()).execute(
            token=RAW_TOKEN, client_address="192.0.2.1"
        )
    assert error.value.retry_after_seconds == 71
