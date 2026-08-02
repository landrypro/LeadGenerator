import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from backend.app.domain.identity import MembershipRole
from backend.app.domain.provisioning import InvitationMessage
from backend.app.infrastructure.invitations import MailpitInvitationDelivery

pytestmark = pytest.mark.integration


def mailpit_configuration() -> tuple[int, str]:
    smtp_port = os.environ.get("TEST_MAILPIT_SMTP_PORT", "")
    api_url = os.environ.get("TEST_MAILPIT_API_URL", "")
    if not smtp_port or not api_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_MAILPIT_SMTP_PORT et TEST_MAILPIT_API_URL sont obligatoires.")
        pytest.skip("Mailpit est requis pour ce test d’intégration.")
    return int(smtp_port), api_url.rstrip("/")


async def test_mailpit_adapter_sends_exactly_one_minimal_local_message() -> None:
    smtp_port, api_url = mailpit_configuration()
    recipient = f"mailpit-{uuid4()}@example.ca"
    token = "A" * 43
    link = f"http://localhost:5173/accept-invitation#token={token}"
    delivery = MailpitInvitationDelivery(
        host="127.0.0.1",
        port=smtp_port,
        timeout_seconds=5,
        from_email="no-reply@prospect.local",
    )
    await delivery.send(
        InvitationMessage(
            recipient_email=recipient,
            organization_name="Organisation Mailpit",
            role=MembershipRole.ADMIN,
            expires_at=datetime.now(UTC) + timedelta(days=3),
            invitation_link=link,
        )
    )

    async with httpx.AsyncClient(base_url=api_url, timeout=5) as client:
        matches = []
        for _ in range(20):
            response = await client.get("/api/v1/messages")
            response.raise_for_status()
            matches = [
                message
                for message in response.json()["messages"]
                if any(address["Address"] == recipient for address in message["To"])
            ]
            if matches:
                break
            await asyncio.sleep(0.05)
        assert len(matches) == 1
        message_response = await client.get(f"/api/v1/message/{matches[0]['ID']}")
        message_response.raise_for_status()
        serialized = message_response.text

    assert link in serialized
    assert "Organisation Mailpit" in serialized
    assert "password" not in serialized.casefold()
    assert "csrf" not in serialized.casefold()
    assert "organization_id" not in serialized.casefold()
