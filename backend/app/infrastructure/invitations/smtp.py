from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from ...application.errors import InvitationDeliveryFailed, InvitationDeliveryUnavailable
from ...domain.provisioning import InvitationMessage


class DisabledInvitationDelivery:
    @property
    def is_configured(self) -> bool:
        return False

    async def send(self, message: InvitationMessage) -> None:
        del message
        raise InvitationDeliveryUnavailable


class MailpitInvitationDelivery:
    def __init__(self, *, host: str, port: int, timeout_seconds: float, from_email: str) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._from_email = from_email

    @property
    def is_configured(self) -> bool:
        return True

    async def send(self, message: InvitationMessage) -> None:
        email = EmailMessage()
        email["From"] = self._from_email
        email["To"] = message.recipient_email
        email["Subject"] = f"Invitation à rejoindre {message.organization_name}"
        email.set_content(
            "\n".join(
                (
                    "Vous avez été invité à rejoindre Prospect CRM.",
                    f"Organisation : {message.organization_name}",
                    f"Rôle : {message.role.value}",
                    f"Expiration : {message.expires_at.isoformat()}",
                    "",
                    message.invitation_link,
                    "",
                    "Ignorez ce message si vous n’attendiez pas cette invitation.",
                )
            )
        )
        try:
            await asyncio.to_thread(self._send, email)
        except (OSError, smtplib.SMTPException) as error:
            raise InvitationDeliveryFailed from error

    def _send(self, email: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds) as client:
            client.send_message(email)
