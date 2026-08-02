from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from uuid import UUID


class HmacCursorCodec:
    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("La clé de signature des curseurs doit contenir au moins 32 octets.")
        self._key = hmac.new(key, b"prospect-pagination-v1", hashlib.sha256).digest()

    def encode(self, created_at: datetime, item_id: UUID) -> str:
        if created_at.tzinfo is None:
            raise ValueError("La date du curseur doit inclure un fuseau horaire.")
        payload = json.dumps(
            {"created_at": created_at.isoformat(), "id": str(item_id)},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature = hmac.new(self._key, payload, hashlib.sha256).digest()
        return f"{_encode(payload)}.{_encode(signature)}"

    def decode(self, cursor: str | None) -> tuple[datetime | None, UUID | None]:
        if cursor is None:
            return None, None
        if not 1 <= len(cursor) <= 512:
            raise ValueError("Le curseur est invalide.")
        try:
            payload_part, signature_part = cursor.split(".", maxsplit=1)
            payload = _decode(payload_part)
            supplied_signature = _decode(signature_part)
            expected_signature = hmac.new(self._key, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("signature")
            data = json.loads(payload)
            created_at = datetime.fromisoformat(str(data["created_at"]))
            item_id = UUID(str(data["id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Le curseur est invalide.") from error
        if created_at.tzinfo is None:
            raise ValueError("Le curseur est invalide.")
        return created_at, item_id


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(f"{value}{'=' * (-len(value) % 4)}")
