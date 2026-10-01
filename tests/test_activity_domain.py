from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.domain.activity import (
    ActivityDirection,
    ActivityType,
    ActivityValidationError,
    ContactPermissionSnapshot,
    ProspectActivityDraft,
    ProspectTaskDraft,
    TaskPriority,
    validate_activity_draft,
    validate_task_draft,
)
from backend.app.domain.identity import CAPABILITIES_BY_ROLE, MembershipRole
from backend.app.infrastructure.postgres.models import Base

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


def test_activity_validation_normalizes_text_and_rejects_future_activity() -> None:
    draft = ProspectActivityDraft(
        prospect_id=uuid4(),
        activity_type=ActivityType.CALL,
        direction=ActivityDirection.OUTBOUND,
        summary="  Appel de qualification  ",
        note="  Message laissé  ",
        occurred_at=NOW - timedelta(minutes=1),
        permission_snapshot=ContactPermissionSnapshot.ALLOWED,
    )

    validated = validate_activity_draft(draft, now=NOW)

    assert validated.summary == "Appel de qualification"
    assert validated.note == "Message laissé"

    with pytest.raises(ActivityValidationError, match="futur"):
        validate_activity_draft(
            ProspectActivityDraft(
                prospect_id=uuid4(),
                activity_type=ActivityType.NOTE,
                direction=ActivityDirection.INTERNAL,
                summary="À venir",
                occurred_at=NOW + timedelta(seconds=1),
            ),
            now=NOW,
        )


def test_activity_correction_requires_a_link_and_a_reason() -> None:
    with pytest.raises(ActivityValidationError, match="motif"):
        validate_activity_draft(
            ProspectActivityDraft(
                prospect_id=uuid4(),
                activity_type=ActivityType.NOTE,
                direction=ActivityDirection.INTERNAL,
                summary="Correction",
                occurred_at=NOW,
                correction_of_activity_id=uuid4(),
            ),
            now=NOW,
        )


def test_activity_validation_requires_a_direction_for_contact_declarations() -> None:
    with pytest.raises(ActivityValidationError, match="entrant ou sortant"):
        validate_activity_draft(
            ProspectActivityDraft(
                prospect_id=uuid4(),
                activity_type=ActivityType.EMAIL,
                direction=ActivityDirection.INTERNAL,
                summary="Courriel",
                occurred_at=NOW,
            ),
            now=NOW,
        )


def test_task_validation_rejects_reminder_after_due_date() -> None:
    with pytest.raises(ActivityValidationError, match="postérieur"):
        validate_task_draft(
            ProspectTaskDraft(
                prospect_id=uuid4(),
                title="Relancer le prospect",
                due_at=NOW + timedelta(days=1),
                reminder_at=NOW + timedelta(days=2),
                priority=TaskPriority.HIGH,
            )
        )


def test_activity_and_task_text_limits_match_the_approved_specification() -> None:
    with pytest.raises(ActivityValidationError, match="résumé"):
        validate_activity_draft(
            ProspectActivityDraft(
                prospect_id=uuid4(),
                activity_type=ActivityType.NOTE,
                direction=ActivityDirection.INTERNAL,
                summary="x" * 161,
                occurred_at=NOW,
            ),
            now=NOW,
        )

    with pytest.raises(ActivityValidationError, match="titre"):
        validate_task_draft(
            ProspectTaskDraft(
                prospect_id=uuid4(),
                title="x" * 161,
                due_at=NOW + timedelta(days=1),
            )
        )

    with pytest.raises(ActivityValidationError, match="description"):
        validate_task_draft(
            ProspectTaskDraft(
                prospect_id=uuid4(),
                title="Relancer le prospect",
                description="x" * 2_001,
                due_at=NOW + timedelta(days=1),
            )
        )


def test_activity_and_task_capabilities_follow_the_role_matrix() -> None:
    assert "activities:correct:any" in CAPABILITIES_BY_ROLE[MembershipRole.ADMIN]
    assert "tasks:manage" in CAPABILITIES_BY_ROLE[MembershipRole.MANAGER]
    assert "activities:correct:any" not in CAPABILITIES_BY_ROLE[MembershipRole.SALES]
    assert "tasks:manage" not in CAPABILITIES_BY_ROLE[MembershipRole.SALES]


def test_activity_task_models_are_registered_in_the_schema_metadata() -> None:
    assert {"prospect_activities", "prospect_tasks", "prospect_task_events"} <= set(Base.metadata.tables)
