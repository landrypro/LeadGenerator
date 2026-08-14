from uuid import uuid4

import pytest

from backend.app.domain.audit import (
    AuditAction,
    AuditActorKind,
    AuditEventDraft,
    AuditScope,
    AuditSource,
    InvalidAuditMetadata,
)
from backend.app.domain.prospect import (
    ContactChannelDraft,
    ContactChannelType,
    ProspectDraft,
    ProspectOrigin,
    ProspectValidationError,
    ProvenanceSourceKind,
    ensure_channel_provenance_is_allowed,
)


def test_prospect_draft_rejects_invalid_alias_and_priority() -> None:
    with pytest.raises(ProspectValidationError):
        ProspectDraft(
            organization_id=uuid4(),
            internal_alias=" ",
            origin=ProspectOrigin.MANUAL,
            source_label="Saisie manuelle",
        )

    with pytest.raises(ProspectValidationError):
        ProspectDraft(
            organization_id=uuid4(),
            internal_alias="Entreprise",
            origin=ProspectOrigin.MANUAL,
            source_label="Saisie manuelle",
            priority=6,
        )


def test_contact_channel_requires_exactly_one_target() -> None:
    organization_id = uuid4()
    provenance_id = uuid4()
    prospect_id = uuid4()
    contact_id = uuid4()

    with pytest.raises(ProspectValidationError):
        ContactChannelDraft(
            organization_id=organization_id,
            prospect_id=prospect_id,
            contact_id=contact_id,
            channel_type=ContactChannelType.EMAIL,
            value="qa@example.ca",
            value_normalized="qa@example.ca",
            provenance_id=provenance_id,
        )

    with pytest.raises(ProspectValidationError):
        ContactChannelDraft(
            organization_id=organization_id,
            channel_type=ContactChannelType.EMAIL,
            value="qa@example.ca",
            value_normalized="qa@example.ca",
            provenance_id=provenance_id,
        )


def test_google_maps_cannot_be_used_as_persistent_channel_provenance() -> None:
    with pytest.raises(ProspectValidationError):
        ensure_channel_provenance_is_allowed(ProvenanceSourceKind.GOOGLE_MAPS)

    ensure_channel_provenance_is_allowed(ProvenanceSourceKind.CSV)


def test_prospect_audit_metadata_is_minimal_and_rejects_channel_values() -> None:
    event = AuditEventDraft(
        id=uuid4(),
        scope=AuditScope.TENANT,
        action=AuditAction.CHANNEL_CREATED,
        entity_type="contact_channel",
        entity_id=uuid4(),
        actor_kind=AuditActorKind.USER,
        actor_id=uuid4(),
        organization_id=uuid4(),
        request_id="prospect-domain",
        correlation_id="prospect-domain",
        source=AuditSource.API,
        metadata={"channel_type": "email", "target_type": "prospect"},
    )

    assert dict(event.metadata) == {"channel_type": "email", "target_type": "prospect"}

    with pytest.raises(InvalidAuditMetadata):
        AuditEventDraft(
            id=uuid4(),
            scope=AuditScope.TENANT,
            action=AuditAction.CHANNEL_CREATED,
            entity_type="contact_channel",
            entity_id=uuid4(),
            actor_kind=AuditActorKind.USER,
            actor_id=uuid4(),
            organization_id=uuid4(),
            request_id="prospect-domain",
            correlation_id="prospect-domain",
            source=AuditSource.API,
            metadata={"channel_type": "email", "target_type": "prospect", "value": "qa@example.ca"},
        )


def test_prospect_audit_accepts_creation_origin() -> None:
    event = AuditEventDraft(
        id=uuid4(),
        scope=AuditScope.TENANT,
        action=AuditAction.PROSPECT_CREATED,
        entity_type="prospect",
        entity_id=uuid4(),
        actor_kind=AuditActorKind.USER,
        actor_id=uuid4(),
        organization_id=uuid4(),
        request_id="prospect-created",
        correlation_id="prospect-created",
        source=AuditSource.API,
        metadata={"origin": "google_place"},
    )

    assert dict(event.metadata) == {"origin": "google_place"}
