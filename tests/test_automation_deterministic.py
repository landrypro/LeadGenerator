from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from backend.app.domain.automation import (
    AUTOMATION_PREPARE_CAPABILITY,
    AutomationChannel,
    AutomationFeatureFlags,
    AutomationValidationError,
    DeterministicAutomationEngine,
    EvaluationContext,
    FireLevel,
    FireReasonCode,
    NextAction,
    PlaybookCode,
    PlaybookVersion,
    SubjectType,
)
from backend.app.domain.prospect import ContactPermissionStatus

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000002")
MEMBERSHIP_ID = UUID("00000000-0000-0000-0000-000000000003")
SUBJECT_ID = UUID("00000000-0000-0000-0000-000000000004")


def playbook() -> PlaybookVersion:
    return PlaybookVersion(
        playbook_id="pb-new-prospect",
        code=PlaybookCode.NEW_PROSPECT,
        version=1,
        ruleset_version="FEU-1.0",
    )


def context(**changes: object) -> EvaluationContext:
    base: dict[str, object] = {
        "organization_id": ORG_ID,
        "actor_id": ACTOR_ID,
        "actor_membership_id": MEMBERSHIP_ID,
        "role": "commercial",
        "capabilities": frozenset({AUTOMATION_PREPARE_CAPABILITY}),
        "subject_type": SubjectType.PROSPECT,
        "subject_id": SUBJECT_ID,
        "playbook": playbook(),
        "channel": AutomationChannel.INTERNAL,
        "permission": ContactPermissionStatus.ALLOWED,
        "organization_active": True,
        "member_active": True,
        "global_enabled": True,
        "organization_enabled": True,
        "playbook_enabled": True,
        "identity_present": True,
        "data_fresh": True,
        "opposition_present": False,
        "crm_version": 4,
        "suspension_generation": 0,
        "evaluated_at": NOW,
    }
    base.update(changes)
    return EvaluationContext(**base)  # type: ignore[arg-type]


def test_green_decision_is_deterministic_and_prepares_without_effect() -> None:
    engine = DeterministicAutomationEngine()
    current = context()

    first = engine.evaluate(current)
    second = engine.evaluate(current)
    plan = engine.prepare(current)

    assert first == second
    assert first.level is FireLevel.GREEN
    assert first.reason_codes == (FireReasonCode.READY,)
    assert first.next_action is NextAction.PREPARE
    assert plan.effect_free is True
    assert plan.crm_mutation_count == 0
    assert plan.proposed_actions[0].effect_allowed is False
    assert plan.is_current(current, at=NOW + timedelta(minutes=1))


def test_automation_flags_are_closed_by_default_and_most_restrictive_scope_wins() -> None:
    default = AutomationFeatureFlags()

    assert default.preparation_enabled is False
    assert default.disabled_scope == "global"
    assert AutomationFeatureFlags(global_enabled=True).disabled_scope == "organization"
    assert AutomationFeatureFlags(global_enabled=True, organization_enabled=True).disabled_scope == "playbook"
    assert (
        AutomationFeatureFlags(
            global_enabled=True,
            organization_enabled=True,
            playbook_enabled=True,
        ).preparation_enabled
        is True
    )


def test_red_block_has_priority_over_permission_unknown() -> None:
    engine = DeterministicAutomationEngine()
    decision = engine.evaluate(
        context(
            global_enabled=False,
            permission=ContactPermissionStatus.UNKNOWN,
        )
    )

    assert decision.level is FireLevel.RED
    assert decision.next_action is NextAction.REFUSE
    assert FireReasonCode.AUTOMATION_DISABLED in decision.reason_codes
    assert FireReasonCode.PERMISSION_UNKNOWN not in decision.reason_codes


def test_do_not_contact_is_red_even_when_every_other_input_is_ready() -> None:
    decision = DeterministicAutomationEngine().evaluate(context(permission=ContactPermissionStatus.DO_NOT_CONTACT))

    assert decision.level is FireLevel.RED
    assert decision.reason_codes == (FireReasonCode.PERMISSION_DENIED,)
    assert decision.next_action is NextAction.REFUSE


def test_unknown_permission_is_yellow_and_never_green() -> None:
    decision = DeterministicAutomationEngine().evaluate(context(permission=ContactPermissionStatus.UNKNOWN))

    assert decision.level is FireLevel.YELLOW
    assert decision.reason_codes == (FireReasonCode.PERMISSION_UNKNOWN,)
    assert decision.next_action is NextAction.VERIFY


def test_missing_identity_or_stale_data_is_to_verify() -> None:
    decision = DeterministicAutomationEngine().evaluate(context(identity_present=False, data_fresh=False))

    assert decision.level is FireLevel.TO_VERIFY
    assert decision.next_action is NextAction.VERIFY
    assert decision.reason_codes == (
        FireReasonCode.IDENTITY_MISSING,
        FireReasonCode.DATA_STALE,
    )


def test_preflight_becomes_obsolete_when_crm_snapshot_changes_or_expires() -> None:
    engine = DeterministicAutomationEngine()
    current = context()
    plan = engine.prepare(current)

    assert not plan.is_current(replace(current, crm_version=5), at=NOW + timedelta(minutes=1))
    assert not plan.is_current(current, at=NOW + timedelta(minutes=15))
    assert not plan.is_current(current, at=NOW + timedelta(minutes=16))


def test_playbook_version_and_preflight_are_immutable() -> None:
    version = playbook()
    plan = DeterministicAutomationEngine().prepare(context())

    with pytest.raises(FrozenInstanceError):
        version.version = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        plan.crm_mutation_count = 1  # type: ignore[misc]


def test_invalid_context_or_ttl_is_rejected() -> None:
    with pytest.raises(AutomationValidationError):
        context(evaluated_at=datetime(2026, 10, 1, 15, 0))

    with pytest.raises(AutomationValidationError):
        DeterministicAutomationEngine().prepare(context(), ttl=timedelta(0))
