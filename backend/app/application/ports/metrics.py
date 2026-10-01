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
MetricsOutcome = Literal["accepted", "rejected", "failed", "expired", "contended", "unavailable", "warning"]
QuotaScope = Literal["user", "organization"]
GrantAction = Literal["issued", "claimed", "rejected", "resolved"]
GoogleApi = Literal["places_text_search", "places_autocomplete", "places_details", "maps_static"]
UsageApi = Literal[
    "places_text_search_quota",
    "places_text_search",
    "places_autocomplete",
    "places_details",
    "maps_static",
    "csv_export",
    "csv_import",
]
CrmCommand = Literal["activity", "task"]
CrmTaskAction = Literal["created", "updated", "completed", "cancelled", "reopened", "reminder_changed"]
CrmOpportunityAction = Literal["created", "updated", "stage_changed", "reopened", "portfolio"]


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

    def record_usage_registry_write(self, api: UsageApi, outcome: MetricsOutcome, policy_code: str) -> None: ...

    def record_crm_activity_command(self, activity_type: str, result: MetricsOutcome) -> None: ...

    def record_crm_task_command(self, action: CrmTaskAction, result: MetricsOutcome) -> None: ...

    def record_crm_task_version_conflict(self) -> None: ...

    def record_crm_timeline_request(self, result: MetricsOutcome) -> None: ...

    def record_crm_opportunity_command(self, action: CrmOpportunityAction, result: MetricsOutcome) -> None: ...

    def record_crm_opportunity_transition(self, from_stage: str, to_stage: str, result: MetricsOutcome) -> None: ...

    def record_crm_opportunity_version_conflict(self, action: CrmOpportunityAction) -> None: ...


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

    def record_usage_registry_write(self, api: UsageApi, outcome: MetricsOutcome, policy_code: str) -> None:
        del api, outcome, policy_code

    def record_crm_activity_command(self, activity_type: str, result: MetricsOutcome) -> None:
        del activity_type, result

    def record_crm_task_command(self, action: CrmTaskAction, result: MetricsOutcome) -> None:
        del action, result

    def record_crm_task_version_conflict(self) -> None:
        return None

    def record_crm_timeline_request(self, result: MetricsOutcome) -> None:
        del result

    def record_crm_opportunity_command(self, action: CrmOpportunityAction, result: MetricsOutcome) -> None:
        del action, result

    def record_crm_opportunity_transition(self, from_stage: str, to_stage: str, result: MetricsOutcome) -> None:
        del from_stage, to_stage, result

    def record_crm_opportunity_version_conflict(self, action: CrmOpportunityAction) -> None:
        del action
