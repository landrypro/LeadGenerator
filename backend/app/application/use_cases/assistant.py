from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from time import perf_counter
from typing import Literal
from uuid import UUID

from ...domain.assistant import (
    ACTIVE_ASSISTANT_INTENTS,
    ASSISTANT_PLAN_ITEM_LIMIT,
    GUIDED_ASSISTANT_INTENTS,
    AssistantFallbackReason,
    AssistantIntent,
    AssistantIntentCode,
    AssistantPlan,
    AssistantPlanOutcome,
    AssistantResultCode,
    AssistantValidationError,
    guided_assistant_payload,
    parse_assistant_intent,
)
from ..ports.assistant import (
    AssistantInterpretationRequest,
    AssistantInterpreterPort,
    AssistantProtection,
    AssistantProtectionUnavailable,
    AssistantProviderUnavailable,
    AssistantScopeReader,
)
from ..ports.clock import Clock
from ..ports.metrics import MetricsRecorder, NullMetricsRecorder
from ..tenancy import TenantContext


class AssistantDisabled(RuntimeError):
    pass


class AssistantCommandInvalid(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CreateAssistantPlanCommand:
    context: TenantContext
    membership_id: UUID
    locale: str
    input_mode: Literal["free_text", "guided"]
    user_text: str | None
    suggestion_code: str | None
    can_read_organization: bool
    rollout_enabled: bool = True


class CreateAssistantPlanUseCase:
    def __init__(
        self,
        interpreter: AssistantInterpreterPort,
        protection: AssistantProtection,
        reader: AssistantScopeReader,
        clock: Clock,
        *,
        global_enabled: bool,
        max_text_characters: int,
        maximum_scope: int,
        timeout_seconds: float,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._interpreter = interpreter
        self._protection = protection
        self._reader = reader
        self._clock = clock
        self._global_enabled = global_enabled
        self._max_text_characters = max_text_characters
        self._maximum_scope = maximum_scope
        self._timeout_seconds = timeout_seconds
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(self, command: CreateAssistantPlanCommand) -> AssistantPlanOutcome:
        if (
            not self._global_enabled
            or not command.rollout_enabled
            or not await self._reader.organization_enabled(command.context)
        ):
            raise AssistantDisabled
        if command.locale not in {"fr-CA", "en-CA"}:
            raise AssistantCommandInvalid("La locale Assistant est invalide.")
        intent = await self._interpret(command)
        if isinstance(intent, AssistantPlanOutcome):
            self._metrics.record_assistant_request(intent.result_code.value)
            return intent
        outcome = await self._build_outcome(command, intent)
        self._metrics.record_assistant_request(outcome.result_code.value)
        return outcome

    async def _interpret(self, command: CreateAssistantPlanCommand) -> AssistantIntent | AssistantPlanOutcome:
        if command.input_mode == "guided":
            if command.user_text is not None or command.suggestion_code is None:
                raise AssistantCommandInvalid("La suggestion guidée est invalide.")
            try:
                code = AssistantIntentCode(command.suggestion_code)
                guided_payload = guided_assistant_payload(code, maximum_scope=self._maximum_scope)
                return parse_assistant_intent(guided_payload, maximum_scope=self._maximum_scope)
            except (ValueError, AssistantValidationError) as error:
                raise AssistantCommandInvalid("La suggestion guidée est invalide.") from error
        if command.input_mode != "free_text" or command.suggestion_code is not None or command.user_text is None:
            raise AssistantCommandInvalid("La demande Assistant est invalide.")
        text = command.user_text.strip()
        if not text or len(text) > self._max_text_characters:
            raise AssistantCommandInvalid("Le texte Assistant est invalide.")
        try:
            reservation = await self._protection.reserve(
                organization_id=command.context.organization_id,
                user_id=command.context.actor_id,
                now=self._clock.now(),
            )
        except AssistantProtectionUnavailable:
            return self._fallback(AssistantFallbackReason.PROVIDER_UNAVAILABLE)
        if not reservation.allowed:
            return self._fallback(AssistantFallbackReason.QUOTA_BLOCKED)
        request = AssistantInterpretationRequest(
            request_id=command.context.request_id,
            schema_version=1,
            locale=command.locale,
            user_text_ephemeral=text,
            allowed_intent_codes=tuple(code.value for code in ACTIVE_ASSISTANT_INTENTS),
            allowed_playbook_codes=("new_prospect",),
            maximum_scope_hint=self._maximum_scope,
            correlation_id=command.context.request_id,
        )
        started_at = perf_counter()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                raw = await self._interpreter.interpret(request)
        except TimeoutError:
            self._metrics.record_assistant_provider("unavailable", perf_counter() - started_at)
            await self._safe_provider_failure()
            return self._fallback(AssistantFallbackReason.TIMEOUT)
        except AssistantProviderUnavailable:
            self._metrics.record_assistant_provider("unavailable", perf_counter() - started_at)
            await self._safe_provider_failure()
            return self._fallback(AssistantFallbackReason.PROVIDER_UNAVAILABLE)
        try:
            intent = parse_assistant_intent(raw, maximum_scope=self._maximum_scope)
        except (AssistantValidationError, TypeError):
            self._metrics.record_assistant_provider("failed", perf_counter() - started_at)
            await self._safe_provider_failure()
            return self._fallback(AssistantFallbackReason.INTENT_OUTPUT_INVALID)
        self._metrics.record_assistant_provider("accepted", perf_counter() - started_at)
        with suppress(AssistantProtectionUnavailable):
            await self._protection.record_provider_success()
        return intent

    async def _build_outcome(
        self, command: CreateAssistantPlanCommand, intent: AssistantIntent
    ) -> AssistantPlanOutcome:
        if intent.intent_code is AssistantIntentCode.CLARIFY_REQUEST:
            return AssistantPlanOutcome(
                result_code=AssistantResultCode.CLARIFICATION_REQUIRED,
                intent=intent,
                plan=None,
                suggestion_codes=GUIDED_ASSISTANT_INTENTS,
            )
        if intent.intent_code is AssistantIntentCode.UNSUPPORTED_REQUEST:
            return AssistantPlanOutcome(
                result_code=AssistantResultCode.INTENT_NOT_SUPPORTED,
                intent=intent,
                plan=None,
                suggestion_codes=GUIDED_ASSISTANT_INTENTS,
            )
        if intent.intent_code is AssistantIntentCode.REBALANCE_OPEN_PROSPECTS and not command.can_read_organization:
            return AssistantPlanOutcome(
                result_code=AssistantResultCode.INTENT_NOT_SUPPORTED,
                intent=intent,
                plan=None,
                suggestion_codes=GUIDED_ASSISTANT_INTENTS,
            )
        snapshot = await self._reader.resolve(
            command.context,
            membership_id=command.membership_id,
            intent_code=intent.intent_code,
            scope_kind=intent.scope_kind,
            collective=(
                command.can_read_organization and intent.intent_code is AssistantIntentCode.REBALANCE_OPEN_PROSPECTS
            ),
            item_limit=min(intent.scope_limit, ASSISTANT_PLAN_ITEM_LIMIT),
        )
        if not snapshot.organization_enabled:
            raise AssistantDisabled
        bounded = min(snapshot.resolved_count, intent.scope_limit) if snapshot.resolved_count is not None else None
        return AssistantPlanOutcome(
            result_code=AssistantResultCode.PLAN_READY,
            intent=intent,
            plan=AssistantPlan(
                title_key=intent.explanation_key,
                resolved_count=snapshot.resolved_count,
                bounded_count=bounded,
                control_codes=("read_only", "server_resolved_scope", "no_provider_tools"),
                not_performed_codes=("no_crm_write", "no_preflight", "no_job", "no_external_send"),
                next_step_code="review_plan",
                items=snapshot.items,
                next_cursor=snapshot.next_cursor,
            ),
            suggestion_codes=(),
        )

    async def _safe_provider_failure(self) -> None:
        with suppress(AssistantProtectionUnavailable):
            await self._protection.record_provider_failure()

    @staticmethod
    def _fallback(reason: AssistantFallbackReason) -> AssistantPlanOutcome:
        return AssistantPlanOutcome(
            result_code=AssistantResultCode.FALLBACK_GUIDED,
            intent=None,
            plan=None,
            suggestion_codes=GUIDED_ASSISTANT_INTENTS,
            fallback_reason=reason,
        )
