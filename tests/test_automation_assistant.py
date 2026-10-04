import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest

from backend.app.application.ports.assistant import AssistantQuotaReservation, AssistantScopeSnapshot
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.assistant import CreateAssistantPlanCommand, CreateAssistantPlanUseCase
from backend.app.domain.assistant import (
    AssistantIntentCode,
    AssistantResultCode,
    AssistantValidationError,
    parse_assistant_intent,
)
from backend.app.infrastructure.assistant.fake import FakeAssistantInterpreter


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 10, 3, 12, tzinfo=UTC)


@dataclass
class Protection:
    allowed: bool = True
    reservations: int = 0

    async def reserve(self, **_: object) -> AssistantQuotaReservation:
        self.reservations += 1
        return AssistantQuotaReservation(self.allowed, None if self.allowed else "user", 60)

    async def record_provider_success(self) -> None:
        return None

    async def record_provider_failure(self) -> None:
        return None


class Reader:
    async def organization_enabled(self, context: TenantContext) -> bool:
        del context
        return True

    async def resolve(self, context: TenantContext, **_: object) -> AssistantScopeSnapshot:
        del context
        return AssistantScopeSnapshot(resolved_count=75, organization_enabled=True)


def command(*, mode: str = "free_text", text: str | None = "Montre mes prospects ouverts", code: str | None = None):
    return CreateAssistantPlanCommand(
        context=TenantContext(UUID(int=1), UUID(int=2), "assistant-test"),
        membership_id=UUID(int=3),
        locale="fr-CA",
        input_mode=mode,  # type: ignore[arg-type]
        user_text=text,
        suggestion_code=code,
        can_read_organization=True,
    )


def use_case(protection: Protection) -> CreateAssistantPlanUseCase:
    return CreateAssistantPlanUseCase(
        FakeAssistantInterpreter(),
        protection,
        Reader(),
        FixedClock(),
        global_enabled=True,
        max_text_characters=500,
        maximum_scope=50,
        timeout_seconds=2,
    )


def test_free_text_builds_a_bounded_read_only_plan() -> None:
    protection = Protection()
    outcome = asyncio.run(use_case(protection).execute(command()))

    assert outcome.result_code is AssistantResultCode.PLAN_READY
    assert outcome.intent is not None
    assert outcome.intent.intent_code is AssistantIntentCode.SCOPE_OPEN_PROSPECTS
    assert outcome.plan is not None
    assert outcome.plan.resolved_count == 75
    assert outcome.plan.bounded_count == 50
    assert outcome.plan.not_performed_codes == ("no_crm_write", "no_preflight", "no_job", "no_external_send")
    assert protection.reservations == 1


def test_guided_suggestion_bypasses_provider_quota() -> None:
    protection = Protection(allowed=False)
    outcome = asyncio.run(
        use_case(protection).execute(command(mode="guided", text=None, code="prepare_new_prospect_followup"))
    )

    assert outcome.result_code is AssistantResultCode.PLAN_READY
    assert protection.reservations == 0


def test_quota_failure_falls_back_to_guided_mode() -> None:
    outcome = asyncio.run(use_case(Protection(allowed=False)).execute(command()))

    assert outcome.result_code is AssistantResultCode.FALLBACK_GUIDED
    assert outcome.plan is None
    assert len(outcome.suggestion_codes) == 3


def test_closed_intent_schema_rejects_unknown_properties() -> None:
    with pytest.raises(AssistantValidationError):
        parse_assistant_intent(
            {
                "schema_version": 1,
                "intent_code": "scope_open_prospects",
                "playbook_code": None,
                "scope_kind": "assigned_open_prospects",
                "scope_limit": 50,
                "clarification_required": False,
                "clarification_key": None,
                "explanation_key": "plan_scope_open_prospects",
                "tool_call": "forbidden",
            }
        )
