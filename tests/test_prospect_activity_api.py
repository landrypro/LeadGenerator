from datetime import UTC, datetime
from uuid import uuid4

from backend.app.domain.activity import (
    ActivityDirection,
    ActivityType,
    ContactPermissionSnapshot,
    ProspectActivityView,
)
from backend.app.domain.pipeline import ProspectStageTransitionView
from backend.app.domain.prospect import ProspectStageCode
from backend.app.presentation.api.routers.prospects import _activity_payload, _timeline_transition_payload
from backend.app.presentation.api.schemas import ActivityCreateRequest


def test_activity_create_request_accepts_an_optional_channel_reference() -> None:
    channel_id = uuid4()

    payload = ActivityCreateRequest.model_validate(
        {
            "activity_type": "email",
            "direction": "outbound",
            "summary": "Courriel déclaré",
            "occurred_at": "2026-09-05T14:00:00Z",
            "contact_channel_id": str(channel_id),
            "idempotency_key": "activity-command-001",
        }
    )

    assert payload.contact_channel_id == channel_id


def test_activity_response_exposes_the_frozen_permission_without_channel_value() -> None:
    now = datetime(2026, 9, 5, 14, tzinfo=UTC)
    channel_id = uuid4()
    activity = ProspectActivityView(
        id=uuid4(),
        organization_id=uuid4(),
        prospect_id=uuid4(),
        actor_id=uuid4(),
        activity_type=ActivityType.EMAIL,
        direction=ActivityDirection.OUTBOUND,
        summary="Courriel déclaré",
        occurred_at=now,
        created_at=now,
        note=None,
        contact_id=uuid4(),
        contact_channel_id=channel_id,
        permission_snapshot=ContactPermissionSnapshot.RESTRICTED,
        correction_of_activity_id=None,
        correction_reason=None,
    )

    response = _activity_payload(activity)

    assert response["contact_channel_id"] == str(channel_id)
    assert response["permission_snapshot"] == "restricted"
    assert response["actor_id"] == str(activity.actor_id)
    assert "value" not in response


def test_timeline_transition_response_exposes_only_the_stage_change() -> None:
    now = datetime(2026, 9, 5, 14, tzinfo=UTC)
    transition = ProspectStageTransitionView(
        id=uuid4(),
        prospect_id=uuid4(),
        actor_id=uuid4(),
        from_stage=ProspectStageCode.NEW,
        to_stage=ProspectStageCode.QUALIFYING,
        from_version=1,
        resulting_version=2,
        reason_code=None,
        reason_note=None,
        occurred_at=now,
    )

    response = _timeline_transition_payload(transition)

    assert response["from_stage"] == "new"
    assert response["to_stage"] == "qualifying"
    assert response["occurred_at"] == now.isoformat()
    assert "reason_note" not in response
