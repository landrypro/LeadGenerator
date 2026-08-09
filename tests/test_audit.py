from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.domain.audit import (
    AuditAction,
    AuditActorKind,
    AuditEventDraft,
    AuditScope,
    AuditSource,
    InvalidAuditEvent,
    InvalidAuditMetadata,
)
from backend.app.infrastructure.postgres.audit_recorder import SqlAlchemyAuditRecorder


def _draft(**overrides: object) -> AuditEventDraft:
    values: dict[str, object] = {
        "id": uuid4(),
        "scope": AuditScope.TENANT,
        "action": AuditAction.MEMBERSHIP_ROLE_CHANGED,
        "entity_type": "membership",
        "entity_id": uuid4(),
        "actor_kind": AuditActorKind.USER,
        "actor_id": uuid4(),
        "organization_id": uuid4(),
        "request_id": "request-123",
        "correlation_id": "request-123",
        "source": AuditSource.API,
        "metadata": {"previous_role": "sales", "new_role": "manager"},
    }
    values.update(overrides)
    return AuditEventDraft(**values)  # type: ignore[arg-type]


def test_audit_event_is_normalized_and_immutable() -> None:
    event = _draft(
        action=AuditAction.ORGANIZATION_UPDATED,
        entity_type="organization",
        metadata={"changed_fields": ["timezone", "name"]},
    )

    assert event.metadata == {"changed_fields": ("name", "timezone")}
    with pytest.raises(TypeError):
        event.metadata["secret"] = "forbidden"  # type: ignore[index]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"organization_id": None}, "organisation"),
        ({"actor_id": None}, "acteur"),
        ({"entity_type": "Membership"}, "entité"),
        ({"entity_type": "organization"}, "correspond"),
        ({"scope": AuditScope.PLATFORM}, "portée"),
        ({"request_id": "bad\nrequest"}, "request_id"),
        ({"schema_version": 0}, "schema_version"),
    ],
)
def test_audit_event_rejects_invalid_invariants(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidAuditEvent, match=message):
        _draft(**overrides)


def test_metadata_policy_rejects_unknown_or_sensitive_fields() -> None:
    with pytest.raises(InvalidAuditMetadata, match="clés"):
        _draft(
            action=AuditAction.INVITATION_CREATED,
            entity_type="invitation",
            metadata={
                "role": "sales",
                "invitation_kind": "member",
                "delivery_status": "pending",
                "email": "person@example.ca",
            },
        )


def test_metadata_policy_rejects_free_text_and_non_internal_identifiers() -> None:
    with pytest.raises(InvalidAuditMetadata, match="external_reference"):
        _draft(
            scope=AuditScope.PLATFORM,
            action=AuditAction.ORGANIZATION_SUSPENDED,
            entity_type="organization",
            metadata={
                "reason_code": "security",
                "operation_id": uuid4(),
                "external_reference": "note libre avec espaces",
            },
        )
    with pytest.raises(InvalidAuditMetadata, match="UUID"):
        _draft(
            action=AuditAction.INVITATION_RESEND_REQUESTED,
            entity_type="invitation",
            metadata={"delivery_attempt_id": "external-id"},
        )


class _StubSession:
    def __init__(self, result: object) -> None:
        self.result = result
        self.statement = ""
        self.parameters: dict[str, object] = {}

    async def scalar(self, statement: object, parameters: dict[str, object]) -> object:
        self.statement = str(statement)
        self.parameters = parameters
        return self.result


@pytest.mark.asyncio
async def test_postgres_recorder_uses_the_supplied_session_without_committing() -> None:
    event = _draft()
    session = _StubSession(event.id)
    recorder = SqlAlchemyAuditRecorder(session)  # type: ignore[arg-type]

    recorded_id = await recorder.record(event)

    assert recorded_id == event.id
    assert "app_private.append_audit_event" in session.statement
    assert session.parameters["metadata"] == '{"previous_role":"sales","new_role":"manager"}'


@pytest.mark.asyncio
async def test_postgres_recorder_rejects_an_invalid_database_result() -> None:
    recorder = SqlAlchemyAuditRecorder(_StubSession("not-an-uuid"))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="UUID"):
        await recorder.record(_draft())
