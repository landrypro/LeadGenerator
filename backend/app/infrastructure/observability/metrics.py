from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from threading import Lock

from ...application.ports.metrics import (
    CrmTaskAction,
    GoogleApi,
    GrantAction,
    MetricsOutcome,
    QuotaScope,
    RedisOperation,
)


class PrometheusMetricsRecorder:
    """Adaptateur Prometheus à labels bornés, associé à un seul conteneur applicatif."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._observations: dict[tuple[str, tuple[tuple[str, str], ...]], tuple[int, float]] = {}

    def record_redis_operation(
        self, operation: RedisOperation, outcome: MetricsOutcome, duration_seconds: float
    ) -> None:
        self._observe(
            "marketteo_redis_operation_duration_seconds", {"operation": operation, "outcome": outcome}, duration_seconds
        )

    def record_google_search_lock(self, outcome: MetricsOutcome) -> None:
        self._increment("marketteo_google_search_lock_total", {"outcome": outcome})

    def record_google_search_quota(self, scope: QuotaScope, outcome: MetricsOutcome, policy_code: str) -> None:
        self._increment(
            "marketteo_google_search_quota_total",
            {"scope": scope, "outcome": outcome, "policy_code": policy_code},
        )

    def record_map_grant(self, action: GrantAction, outcome: MetricsOutcome) -> None:
        self._increment("marketteo_google_map_grant_total", {"action": action, "outcome": outcome})

    def record_selection_grant(self, action: GrantAction, outcome: MetricsOutcome) -> None:
        self._increment("marketteo_google_selection_grant_total", {"action": action, "outcome": outcome})

    def record_google_upstream(self, api: GoogleApi, outcome: MetricsOutcome, duration_seconds: float) -> None:
        labels = {"api": api, "outcome": outcome}
        self._increment("marketteo_google_upstream_calls_total", labels)
        self._observe("marketteo_google_upstream_duration_seconds", labels, duration_seconds)

    def record_crm_activity_command(self, activity_type: str, result: MetricsOutcome) -> None:
        self._increment("marketteo_crm_activity_command_total", {"type": activity_type, "result": result})

    def record_crm_task_command(self, action: CrmTaskAction, result: MetricsOutcome) -> None:
        self._increment("marketteo_crm_task_command_total", {"action": action, "result": result})

    def record_crm_task_version_conflict(self) -> None:
        self._increment("marketteo_crm_task_version_conflict_total", {})

    def record_crm_timeline_request(self, result: MetricsOutcome) -> None:
        self._increment("marketteo_crm_timeline_request_total", {"result": result})

    def render(self) -> bytes:
        with self._lock:
            lines = ["# Marketteo CRM metrics; labels are bounded and contain no identifiers."]
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{_labels(labels)} {value}")
            for (name, labels), (count, total) in sorted(self._observations.items()):
                lines.append(f"{name}_count{_labels(labels)} {count}")
                lines.append(f"{name}_sum{_labels(labels)} {total:.9g}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def _increment(self, name: str, labels: Mapping[str, str]) -> None:
        with self._lock:
            self._counters[(name, tuple(sorted(labels.items())))] += 1

    def _observe(self, name: str, labels: Mapping[str, str], duration_seconds: float) -> None:
        with self._lock:
            key = (name, tuple(sorted(labels.items())))
            count, total = self._observations.get(key, (0, 0.0))
            self._observations[key] = (count + 1, total + max(0.0, duration_seconds))


def _labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    escaped = ",".join(f'{name}="{value}"' for name, value in labels)
    return "{" + escaped + "}"
