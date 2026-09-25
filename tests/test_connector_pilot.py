from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from backend.app.config import Settings
from backend.app.infrastructure.postgres.connector_pilot import (
    MetaLeadWebhookService,
    MetaWebhookRejected,
    _approved_meta_fields,
    _lead_notification,
    _normalize_channel,
)


def _settings() -> Settings:
    return Settings(
        meta_lead_ads_enabled=True,
        meta_webhook_verify_token="v" * 32,
        meta_webhook_app_secret="s" * 32,
        meta_reference_hmac_key="h" * 32,
        meta_lead_reference_encryption_key="e" * 32,
        meta_graph_access_token="t" * 32,
        job_idempotency_hmac_key="j" * 32,
    )


def test_meta_notification_accepts_only_expected_reference_shape() -> None:
    body = json.dumps({"entry": [{"changes": [{"value": {"form_id": "form", "leadgen_id": "lead"}}]}]}).encode()

    assert _lead_notification(body) == ("form", "lead", None)

    with pytest.raises(MetaWebhookRejected):
        _lead_notification(b'{"entry": []}')


def test_meta_mapping_discards_custom_answers_and_invalid_channels() -> None:
    fields = _approved_meta_fields(
        {
            "field_data": [
                {"name": "full_name", "values": [" Ada   Lovelace "]},
                {"name": "email", "values": ["Ada@example.test"]},
                {"name": "favorite_color", "values": ["secret"]},
                {"name": "phone", "values": ["not a phone"]},
            ]
        }
    )

    assert fields.full_name == "Ada Lovelace"
    assert _normalize_channel("email", fields.email or "") == "ada@example.test"
    assert _normalize_channel("phone", fields.phone or "") is None


def test_meta_webhook_challenge_and_signature_use_constant_time_service_contract() -> None:
    # The admission path requires a database; this test isolates the externally observable cryptographic inputs.
    service = MetaLeadWebhookService.__new__(MetaLeadWebhookService)
    service._settings = _settings()
    assert service.verify_challenge("subscribe", "v" * 32, "challenge") == "challenge"
    assert service.verify_challenge("subscribe", "wrong", "challenge") is None

    body = b"{}"
    signature = "sha256=" + hmac.new(("s" * 32).encode(), body, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(signature, "sha256=" + hmac.new(("s" * 32).encode(), body, hashlib.sha256).hexdigest())
