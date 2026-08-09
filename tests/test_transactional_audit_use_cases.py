from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.ports.organization import (
    DeliveryFinalizationGatewayResult,
    UpdateMembershipGatewayResult,
    UpdateMembershipResultCode,
)
from backend.app.application.ports.provisioning import ProvisionGatewayResult, ProvisionResultCode
from backend.app.application.tenancy import ActorContext, TenantContext
from backend.app.application.use_cases.organization import UpdateMembershipUseCase
from backend.app.application.use_cases.provisioning import CreateOrganizationUseCase
from backend.app.domain.audit import AuditAction, AuditEventDraft
from backend.app.domain.identity import MembershipRole, MembershipStatus
from backend.app.domain.organization import MemberView, UpdateMembershipCommand
from backend.app.domain.provisioning import (
    InvitationDeliveryStatus,
    InvitationProvisioningView,
    InvitationState,
    InvitationToken,
    OrganizationProvisioningView,
    ProvisioningView,
    ProvisionOrganizationCommand,
)

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


class Clock:
    def now(self) -> datetime:
        return NOW


class Sessions:
    async def revoke_user_before_version(self, user_id: UUID, minimum_valid_version: int) -> None:
        del user_id, minimum_valid_version


class Recorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[AuditEventDraft] = []
        self.fail = fail

    async def record(self, event: AuditEventDraft) -> UUID:
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(event)
        return event.id


class AuditedUnitOfWork:
    def __init__(self, result: object, *, fail_audit: bool = False) -> None:
        self.result = result
        self.mutations = self
        self.audit = Recorder(fail=fail_audit)
        self.committed = False
        self.exited_with: type[BaseException] | None = None

    async def __aenter__(self) -> AuditedUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_value, traceback
        self.exited_with = exc_type

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def update_membership(self, **kwargs: object) -> object:
        del kwargs
        return self.result

    async def provision(self, **kwargs: object) -> object:
        del kwargs
        return self.result

    async def finalize_delivery(self, **kwargs: object) -> DeliveryFinalizationGatewayResult:
        return DeliveryFinalizationGatewayResult(
            transitioned=True,
            invitation_id=kwargs["invitation_id"],  # type: ignore[arg-type]
            delivery_status=InvitationDeliveryStatus.SENT,
            delivery_kind="initial",
        )


class UnitOfWorkFactory:
    def __init__(self, *units: AuditedUnitOfWork) -> None:
        self.units = list(units)

    def __call__(self, context: object) -> AuditedUnitOfWork:
        del context
        return self.units.pop(0)


def _member() -> MemberView:
    return MemberView(
        membership_id=uuid4(),
        user_id=uuid4(),
        email="member@example.ca",
        display_name="Member",
        role=MembershipRole.MANAGER,
        status=MembershipStatus.DISABLED,
        version=2,
        created_at=NOW,
        updated_at=NOW,
    )


async def test_role_and_status_change_records_two_events_before_one_commit() -> None:
    member = _member()
    unit = AuditedUnitOfWork(
        UpdateMembershipGatewayResult(
            UpdateMembershipResultCode.UPDATED,
            member=member,
            user_version=2,
            previous_role=MembershipRole.SALES,
            previous_status=MembershipStatus.ACTIVE,
        )
    )
    use_case = UpdateMembershipUseCase(
        object(),
        Sessions(),
        Clock(),
        UnitOfWorkFactory(unit),  # type: ignore[arg-type]
    )
    context = TenantContext(uuid4(), uuid4(), "request-audit-member")

    await use_case.execute(
        context=context,
        membership_id=member.membership_id,
        command=UpdateMembershipCommand(version=1, role=member.role, status=member.status),
        has_capability=True,
    )

    assert unit.committed is True
    assert [event.action for event in unit.audit.events] == [
        AuditAction.MEMBERSHIP_ROLE_CHANGED,
        AuditAction.MEMBERSHIP_STATUS_CHANGED,
    ]
    assert all(event.correlation_id == context.request_id for event in unit.audit.events)


async def test_audit_failure_prevents_business_commit() -> None:
    member = _member()
    unit = AuditedUnitOfWork(
        UpdateMembershipGatewayResult(
            UpdateMembershipResultCode.UPDATED,
            member=member,
            user_version=2,
            previous_role=MembershipRole.SALES,
        ),
        fail_audit=True,
    )
    use_case = UpdateMembershipUseCase(
        object(),
        Sessions(),
        Clock(),
        UnitOfWorkFactory(unit),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await use_case.execute(
            context=TenantContext(uuid4(), uuid4(), "request-rollback"),
            membership_id=member.membership_id,
            command=UpdateMembershipCommand(version=1, role=member.role),
            has_capability=True,
        )

    assert unit.committed is False
    assert unit.exited_with is RuntimeError


async def test_unchanged_membership_commits_without_audit_event() -> None:
    member = _member()
    unit = AuditedUnitOfWork(UpdateMembershipGatewayResult(UpdateMembershipResultCode.UNCHANGED, member=member))
    use_case = UpdateMembershipUseCase(
        object(),
        Sessions(),
        Clock(),
        UnitOfWorkFactory(unit),  # type: ignore[arg-type]
    )

    await use_case.execute(
        context=TenantContext(uuid4(), uuid4(), "request-noop"),
        membership_id=member.membership_id,
        command=UpdateMembershipCommand(version=member.version, status=member.status),
        has_capability=True,
    )

    assert unit.committed is True
    assert unit.audit.events == []


class TokenGenerator:
    def generate(self) -> InvitationToken:
        return InvitationToken("A" * 43, "f" * 64)


class Delivery:
    is_configured = True

    async def send(self, message: object) -> None:
        del message


def _provisioning_view() -> ProvisioningView:
    return ProvisioningView(
        OrganizationProvisioningView(uuid4(), "Example", "fr-CA", "America/Toronto", "provisioning", 1, NOW, None),
        InvitationProvisioningView(
            uuid4(),
            "admin@example.ca",
            MembershipRole.ADMIN,
            InvitationState.ACTIVE,
            InvitationDeliveryStatus.PENDING,
            NOW + timedelta(days=3),
        ),
        False,
    )


async def test_provisioning_and_delivery_use_two_explicit_audited_transactions() -> None:
    view = _provisioning_view()
    creation = AuditedUnitOfWork(
        ProvisionGatewayResult(ProvisionResultCode.CREATED, view=view, delivery_attempt_id=uuid4())
    )
    finalization = AuditedUnitOfWork(object())
    use_case = CreateOrganizationUseCase(
        object(),
        TokenGenerator(),
        Delivery(),
        Clock(),  # type: ignore[arg-type]
        public_app_url="https://crm.example",
        invitation_ttl_seconds=259_200,
        audited_unit_of_work_factory=UnitOfWorkFactory(creation, finalization),  # type: ignore[arg-type]
    )

    await use_case.execute(
        context=ActorContext(uuid4(), "request-provision"),
        command=ProvisionOrganizationCommand("Example", "fr-CA", "America/Toronto", "admin@example.ca", uuid4()),
        has_platform_capability=True,
    )

    assert [event.action for event in creation.audit.events] == [
        AuditAction.ORGANIZATION_PROVISIONED,
        AuditAction.INITIAL_INVITATION_CREATED,
    ]
    assert [event.action for event in finalization.audit.events] == [AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED]
    assert {event.organization_id for event in creation.audit.events} == {view.organization.id}
    assert {event.organization_id for event in finalization.audit.events} == {view.organization.id}
    assert creation.committed and finalization.committed
