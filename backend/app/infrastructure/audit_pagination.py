from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from ..application.errors import InvalidAuditCursor
from ..application.ports.audit import AuditCursorCodec
from ..domain.audit import AuditEventFilter, AuditScope


class HmacAuditCursorCodec(AuditCursorCodec):
    """Curseur d’audit signé et lié à sa portée, son organisation et ses filtres."""

    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("La clé de signature des curseurs doit contenir au moins 32 octets.")
        self._key = hmac.new(key, b"prospect-audit-pagination-v1", hashlib.sha256).digest()

    def encode(
        self,
        *,
        scope: AuditScope,
        organization_id: UUID | None,
        filters: AuditEventFilter,
        occurred_at: datetime,
        event_id: UUID,
    ) -> str:
        if occurred_at.tzinfo is None:
            raise ValueError("La date du curseur doit inclure un fuseau horaire.")
        payload = {
            "v": 1,
            "scope": scope.value,
            "organization_id": str(organization_id) if organization_id else None,
            "filter": _filter_fingerprint(filters),
            "occurred_at": _utc_iso(occurred_at),
            "id": str(event_id),
        }
        serialized = _serialize(payload)
        signature = hmac.new(self._key, serialized, hashlib.sha256).digest()
        return f"{_encode(serialized)}.{_encode(signature)}"

    def decode(
        self,
        cursor: str | None,
        *,
        scope: AuditScope,
        organization_id: UUID | None,
        filters: AuditEventFilter,
    ) -> tuple[datetime | None, UUID | None]:
        if cursor is None:
            return None, None
        if not 1 <= len(cursor) <= 1024:
            raise InvalidAuditCursor("Le curseur est invalide.")
        try:
            payload_part, signature_part = cursor.split(".", maxsplit=1)
            serialized = _decode(payload_part)
            supplied_signature = _decode(signature_part)
            expected_signature = hmac.new(self._key, serialized, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("signature")
            payload = json.loads(serialized)
            if not isinstance(payload, dict) or set(payload) != {
                "v",
                "scope",
                "organization_id",
                "filter",
                "occurred_at",
                "id",
            }:
                raise ValueError("payload")
            expected_organization = str(organization_id) if organization_id else None
            if (
                payload["v"] != 1
                or payload["scope"] != scope.value
                or payload["organization_id"] != expected_organization
                or payload["filter"] != _filter_fingerprint(filters)
            ):
                raise ValueError("context")
            occurred_at = datetime.fromisoformat(str(payload["occurred_at"]).replace("Z", "+00:00"))
            event_id = UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise InvalidAuditCursor("Le curseur est invalide.") from error
        if occurred_at.tzinfo is None:
            raise InvalidAuditCursor("Le curseur est invalide.")
        return occurred_at.astimezone(UTC), event_id


def _filter_fingerprint(filters: AuditEventFilter) -> str:
    canonical = _serialize(
        {
            "occurred_from": _utc_iso(filters.occurred_from),
            "occurred_to": _utc_iso(filters.occurred_to),
            "action": filters.action.value if filters.action else None,
            "entity_type": filters.entity_type,
            "entity_id": str(filters.entity_id) if filters.entity_id else None,
            "actor_id": str(filters.actor_id) if filters.actor_id else None,
        }
    )
    return hashlib.sha256(canonical).hexdigest()


def _serialize(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("utf-8")


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Une date d’audit doit inclure un fuseau horaire.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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
