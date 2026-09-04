from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Final

_ALLOWED_FIELDS: Final = frozenset(
    {"outcome", "scope", "policy_code", "status_class", "duration_ms", "route", "method"}
)


class _JsonFormatter(logging.Formatter):
    def __init__(self, instance_id: str) -> None:
        super().__init__()
        self._instance_id = instance_id

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", "application_event")
        payload: dict[str, str | int] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "event": event if isinstance(event, str) else "application_event",
            "instance_id": self._instance_id,
        }
        request_id = getattr(record, "request_id", "")
        if isinstance(request_id, str) and request_id:
            payload["request_id"] = request_id
        fields = getattr(record, "technical_fields", {})
        if isinstance(fields, dict):
            for name, value in fields.items():
                if name in _ALLOWED_FIELDS and isinstance(value, str | int):
                    payload[name] = value
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class TechnicalEventLogger:
    """Journal technique à schéma fermé : aucune charge applicative n'est sérialisée."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def info(self, event: str, *, request_id: str = "", **fields: str | int) -> None:
        self._write(logging.INFO, event, request_id=request_id, **fields)

    def warning(self, event: str, *, request_id: str = "", **fields: str | int) -> None:
        self._write(logging.WARNING, event, request_id=request_id, **fields)

    def error(self, event: str, *, request_id: str = "", **fields: str | int) -> None:
        self._write(logging.ERROR, event, request_id=request_id, **fields)

    def _write(self, level: int, event: str, *, request_id: str, **fields: str | int) -> None:
        if event not in _EVENTS:
            event = "application_event"
        safe_fields = {name: value for name, value in fields.items() if name in _ALLOWED_FIELDS}
        self._logger.log(
            level, event, extra={"event": event, "request_id": request_id, "technical_fields": safe_fields}
        )


_EVENTS: Final = frozenset(
    {
        "application_event",
        "http_request_completed",
        "http_request_failed",
        "google_search_lock_acquired",
        "google_search_lock_contended",
        "google_search_lock_release_failed",
        "google_search_quota_consumed",
        "google_search_quota_rejected",
        "google_search_quota_warning",
        "map_grant_issued",
        "map_grant_claimed",
        "map_grant_rejected",
        "selection_grant_issued",
        "selection_grant_resolved",
        "selection_grant_rejected",
        "redis_operation_failed",
        "google_upstream_completed",
        "metrics_access_denied",
    }
)


def configure_application_logging(*, log_format: str, instance_id: str) -> TechnicalEventLogger:
    logger = logging.getLogger("marketteo")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(_JsonFormatter(instance_id))
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    return TechnicalEventLogger(logger)
