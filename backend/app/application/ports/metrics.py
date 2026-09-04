from typing import Literal, Protocol

RedisOperation = Literal[
    "lock_acquire",
    "lock_release",
    "quota_reserve",
    "map_claim",
    "map_finalize",
    "selection_issue",
    "selection_resolve",
]
MetricsOutcome = Literal["accepted", "rejected", "failed", "expired", "contended", "unavailable"]
QuotaScope = Literal["user", "organization"]
GrantAction = Literal["issued", "claimed", "rejected", "resolved"]
GoogleApi = Literal["places_text_search", "maps_static"]


class MetricsRecorder(Protocol):
    """Contrat d'observabilité sans données métier ni dépendance Prometheus."""

    def record_redis_operation(
        self,
        operation: RedisOperation,
        outcome: MetricsOutcome,
        duration_seconds: float,
    ) -> None: ...

    def record_google_search_lock(self, outcome: MetricsOutcome) -> None: ...

    def record_google_search_quota(
        self,
        scope: QuotaScope,
        outcome: MetricsOutcome,
        policy_code: str,
    ) -> None: ...

    def record_map_grant(self, action: GrantAction, outcome: MetricsOutcome) -> None: ...

    def record_selection_grant(self, action: GrantAction, outcome: MetricsOutcome) -> None: ...

    def record_google_upstream(
        self,
        api: GoogleApi,
        outcome: MetricsOutcome,
        duration_seconds: float,
    ) -> None: ...


class NullMetricsRecorder:
    """Doublure explicite, sans effet, utilisée hors des tests d'observabilité."""

    def record_redis_operation(
        self,
        operation: RedisOperation,
        outcome: MetricsOutcome,
        duration_seconds: float,
    ) -> None:
        del operation, outcome, duration_seconds

    def record_google_search_lock(self, outcome: MetricsOutcome) -> None:
        del outcome

    def record_google_search_quota(self, scope: QuotaScope, outcome: MetricsOutcome, policy_code: str) -> None:
        del scope, outcome, policy_code

    def record_map_grant(self, action: GrantAction, outcome: MetricsOutcome) -> None:
        del action, outcome

    def record_selection_grant(self, action: GrantAction, outcome: MetricsOutcome) -> None:
        del action, outcome

    def record_google_upstream(self, api: GoogleApi, outcome: MetricsOutcome, duration_seconds: float) -> None:
        del api, outcome, duration_seconds
