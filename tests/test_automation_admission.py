from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.domain import (
    AUTOMATION_NEW_PROSPECT_JOB_SCHEMA_VERSION,
    AUTOMATION_NEW_PROSPECT_JOB_TYPE,
    INTERNAL_TASK_DESCRIPTION,
    AutomationAdmissionValidationError,
    AutomationFeatureFlags,
    NewProspectAdmission,
    PreparationGuard,
    TaskPriority,
    build_internal_task_draft,
)


def _admission(*, key: str = "admit-prospect-42", identity: str = "new-prospect:42") -> NewProspectAdmission:
    return NewProspectAdmission(
        organization_id=uuid4(),
        prospect_id=uuid4(),
        playbook_version_id=uuid4(),
        requested_by_membership_id=uuid4(),
        preflight_id=uuid4(),
        decision_id=uuid4(),
        correlation_id=uuid4(),
        functional_identity=identity,
        idempotency_key=key,
        admitted_at=datetime(2026, 10, 2, 15, 30, tzinfo=UTC),
    )


def _ready_guard() -> PreparationGuard:
    return PreparationGuard(
        feature_flags=AutomationFeatureFlags(True, True, True),
        preflight_is_current=True,
        decision_is_prepare=True,
        prospect_is_writable=True,
        assigned_membership_id=uuid4(),
        assigned_membership_is_active=True,
    )


def test_admission_hashes_are_deterministic_and_do_not_keep_the_raw_key() -> None:
    admission = _admission()
    same = NewProspectAdmission(
        organization_id=admission.organization_id,
        prospect_id=admission.prospect_id,
        playbook_version_id=admission.playbook_version_id,
        requested_by_membership_id=admission.requested_by_membership_id,
        preflight_id=admission.preflight_id,
        decision_id=admission.decision_id,
        correlation_id=admission.correlation_id,
        functional_identity=admission.functional_identity,
        idempotency_key=admission.idempotency_key,
        admitted_at=admission.admitted_at,
    )

    assert admission.idempotency_key_digest == same.idempotency_key_digest
    assert admission.functional_identity_fingerprint == same.functional_identity_fingerprint
    assert admission.request_fingerprint == same.request_fingerprint
    assert admission.idempotency_key not in admission.idempotency_key_digest
    assert AUTOMATION_NEW_PROSPECT_JOB_TYPE == "automation_new_prospect_prepare"
    assert AUTOMATION_NEW_PROSPECT_JOB_SCHEMA_VERSION == 1


def test_internal_task_is_prepared_with_the_confirmed_contract() -> None:
    admission = _admission()
    guard = _ready_guard()

    task = build_internal_task_draft(admission, prospect_display_name="Atelier Horizon", guard=guard)

    assert task.prospect_id == admission.prospect_id
    assert task.assigned_membership_id == guard.assigned_membership_id
    assert task.title == "Prendre en charge le prospect Atelier Horizon"
    assert task.description == INTERNAL_TASK_DESCRIPTION
    assert task.priority is TaskPriority.NORMAL
    assert task.due_at == admission.admitted_at + timedelta(hours=24)
    assert task.idempotency_key == f"automation-admission:{admission.idempotency_key_digest}"


@pytest.mark.parametrize(
    ("guard", "expected_code"),
    [
        (
            PreparationGuard(
                feature_flags=AutomationFeatureFlags(),
                preflight_is_current=True,
                decision_is_prepare=True,
                prospect_is_writable=True,
                assigned_membership_id=uuid4(),
                assigned_membership_is_active=True,
            ),
            "automation_disabled",
        ),
        (
            PreparationGuard(
                feature_flags=AutomationFeatureFlags(True, True, True),
                preflight_is_current=False,
                decision_is_prepare=True,
                prospect_is_writable=True,
                assigned_membership_id=uuid4(),
                assigned_membership_is_active=True,
            ),
            "preflight_stale",
        ),
        (
            PreparationGuard(
                feature_flags=AutomationFeatureFlags(True, True, True),
                preflight_is_current=True,
                decision_is_prepare=True,
                prospect_is_writable=True,
                assigned_membership_id=None,
                assigned_membership_is_active=False,
            ),
            "owner_unavailable",
        ),
    ],
)
def test_internal_task_requires_a_fresh_double_guard(guard: PreparationGuard, expected_code: str) -> None:
    with pytest.raises(AutomationAdmissionValidationError, match=expected_code):
        build_internal_task_draft(_admission(), prospect_display_name="Atelier Horizon", guard=guard)
