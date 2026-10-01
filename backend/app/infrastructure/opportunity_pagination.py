from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import date, datetime
from uuid import UUID

from ..application.ports.opportunity import OpportunityCursor


class HmacOpportunityCursorCodec:
    """Curseur signé et lié au périmètre visible et aux filtres du portefeuille."""

    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("La clé de signature des curseurs doit contenir au moins 32 octets.")
        self._key = hmac.new(key, b"opportunity-pagination-v1", hashlib.sha256).digest()

    def encode(self, cursor: OpportunityCursor, *, scope: str) -> str:
        if cursor.updated_at.tzinfo is None:
            raise ValueError("La date du curseur doit inclure un fuseau horaire.")
        payload = json.dumps(
            {
                "expected_close_on": cursor.expected_close_on.isoformat(),
                "id": str(cursor.item_id),
                "scope": scope,
                "updated_at": cursor.updated_at.isoformat(),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature = hmac.new(self._key, payload, hashlib.sha256).digest()
        return f"{_encode(payload)}.{_encode(signature)}"

    def decode(self, value: str | None, *, scope: str) -> OpportunityCursor | None:
        if value is None:
            return None
        if not 1 <= len(value) <= 1024:
            raise ValueError("Le curseur est invalide.")
        try:
            payload_part, signature_part = value.split(".", maxsplit=1)
            payload = _decode(payload_part)
            supplied_signature = _decode(signature_part)
            expected_signature = hmac.new(self._key, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("signature")
            data = json.loads(payload)
            if data["scope"] != scope:
                raise ValueError("scope")
            result = OpportunityCursor(
                expected_close_on=date.fromisoformat(str(data["expected_close_on"])),
                updated_at=datetime.fromisoformat(str(data["updated_at"])),
                item_id=UUID(str(data["id"])),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Le curseur est invalide.") from error
        if result.updated_at.tzinfo is None:
            raise ValueError("Le curseur est invalide.")
        return result


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    try:
        decoded = base64.b64decode(f"{value}{'=' * (-len(value) % 4)}", altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Encodage Base64 URL invalide.") from error
    if _encode(decoded) != value:
        raise ValueError("Encodage Base64 URL non canonique.")
    return decoded
