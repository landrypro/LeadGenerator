import base64
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.domain.provisioning import (
    InvitationState,
    ProvisionOrganizationCommand,
    hash_invitation_token,
    invitation_state,
    validate_provision_organization,
)


def test_provisioning_validation_is_canonical_and_unicode_safe() -> None:
    request_id = uuid4()
    first = validate_provision_organization(
        ProvisionOrganizationCommand(
            name="  Société   Été  ",
            locale="fr-CA",
            timezone="America/Toronto",
            first_administrator_email="ADMIN@BÜCHER.example",
            creation_request_id=request_id,
        )
    )
    replay = validate_provision_organization(
        ProvisionOrganizationCommand(
            name="Société Été",
            locale="fr-CA",
            timezone="America/Toronto",
            first_administrator_email="admin@xn--bcher-kva.example",
            creation_request_id=request_id,
        )
    )

    assert first.name == "Société Été"
    assert first.first_administrator_email.normalized == "admin@xn--bcher-kva.example"
    assert first.fingerprint == replay.fingerprint
    assert len(first.fingerprint) == 64


@pytest.mark.parametrize("locale", ["fr-FR", "en-US", ""])
def test_provisioning_rejects_unsupported_locales(locale: str) -> None:
    with pytest.raises(ValueError):
        validate_provision_organization(
            ProvisionOrganizationCommand("Exemple", locale, "America/Toronto", "admin@example.ca", uuid4())
        )


def test_invitation_token_requires_exactly_256_bits_in_base64url() -> None:
    raw = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")

    assert len(raw) == 43
    assert len(hash_invitation_token(raw)) == 64
    for invalid in ("", raw + "a", "!" * 43, "a" * 129):
        with pytest.raises(ValueError):
            hash_invitation_token(invalid)


def test_invitation_state_has_deterministic_terminal_precedence() -> None:
    now = datetime(2026, 7, 23, 12, tzinfo=UTC)

    assert (
        invitation_state(now=now, expires_at=now + timedelta(hours=1), accepted_at=None, revoked_at=None)
        is InvitationState.ACTIVE
    )
    assert invitation_state(now=now, expires_at=now, accepted_at=None, revoked_at=None) is InvitationState.EXPIRED
    assert (
        invitation_state(now=now, expires_at=now - timedelta(days=1), accepted_at=now, revoked_at=None)
        is InvitationState.ACCEPTED
    )
    assert (
        invitation_state(now=now, expires_at=now - timedelta(days=1), accepted_at=None, revoked_at=now)
        is InvitationState.REVOKED
    )
