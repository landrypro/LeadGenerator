from dataclasses import dataclass, field

from .application.ports import (
    AsyncResource,
    MetricsRecorder,
    NullMetricsRecorder,
    TenantUnitOfWorkFactory,
    UnitOfWorkFactory,
    UsageStore,
)
from .application.ports.csv_import import TemporaryCsvFileStore
from .application.use_cases import (
    AcceptInvitationUseCase,
    ActivateRetentionPolicyUseCase,
    AddGoogleProspectsUseCase,
    ArchiveContactChannelUseCase,
    ArchiveContactUseCase,
    ArchiveImportDeclarationUseCase,
    ArchiveProspectUseCase,
    CancelImportDeclarationUseCase,
    ChangeContactPermissionUseCase,
    ChangeOrganizationStatusUseCase,
    CheckReadinessUseCase,
    ConfirmCsvImportUseCase,
    CreateActivityUseCase,
    CreateContactChannelUseCase,
    CreateContactUseCase,
    CreateManualProspectUseCase,
    CreateMemberInvitationUseCase,
    CreateOpportunityUseCase,
    CreateOrganizationUseCase,
    CreateRetentionPolicyUseCase,
    CreateSourceProviderUseCase,
    CreateTaskUseCase,
    DecideAcquisitionUseCase,
    DeclareAcquisitionUseCase,
    DeclareImportUseCase,
    GetAcquisitionUseCase,
    GetContactPermissionUseCase,
    GetCsvImportPreviewUseCase,
    GetCsvImportReportUseCase,
    GetCurrentSessionUseCase,
    GetImportDeclarationUseCase,
    GetMapSnapshotUseCase,
    GetOpportunityUseCase,
    GetOrganizationUseCase,
    GetPipelineBoardUseCase,
    GetProspectUseCase,
    GetRetentionHoldUseCase,
    GetRetentionPolicyUseCase,
    GetSourceProviderUseCase,
    ListAcquisitionsUseCase,
    ListContactChannelsUseCase,
    ListContactsUseCase,
    ListDueRemindersUseCase,
    ListImportDeclarationsUseCase,
    ListMemberInvitationsUseCase,
    ListMembersUseCase,
    ListNextActionsUseCase,
    ListOpportunitiesUseCase,
    ListOpportunityEventsUseCase,
    ListOpportunitySummariesUseCase,
    ListPipelineColumnUseCase,
    ListPipelineStagesUseCase,
    ListPlatformAuditEventsUseCase,
    ListPlatformOrganizationsUseCase,
    ListProspectChannelsUseCase,
    ListProspectStageTransitionsUseCase,
    ListProspectsUseCase,
    ListProspectTimelineUseCase,
    ListRetentionHoldsUseCase,
    ListRetentionPoliciesUseCase,
    ListRetentionReviewsUseCase,
    ListSourceProvidersUseCase,
    ListTasksUseCase,
    ListTenantAuditEventsUseCase,
    LoginUseCase,
    LogoutUseCase,
    MapCsvImportUseCase,
    MoveProspectStageUseCase,
    PlaceRetentionHoldUseCase,
    PreviewInvitationUseCase,
    ReleaseRetentionHoldUseCase,
    ReopenOpportunityUseCase,
    ReopenProspectUseCase,
    ResendInitialInvitationUseCase,
    ResendMemberInvitationUseCase,
    RevokeInitialInvitationUseCase,
    RevokeMemberInvitationUseCase,
    SearchGooglePlacesUseCase,
    SwitchOrganizationUseCase,
    TransitionOpportunityUseCase,
    UpdateMembershipUseCase,
    UpdateOpportunityUseCase,
    UpdateOrganizationUseCase,
    UpdatePipelineStageUseCase,
    UpdateProspectProfileUseCase,
    UpdateRetentionPolicyUseCase,
    UpdateSourceProviderUseCase,
    UpdateTaskUseCase,
    UploadCsvImportUseCase,
    ValidateCsvImportUseCase,
)
from .application.use_cases.dashboard import GetDashboardSummaryUseCase
from .application.use_cases.usage import GetCurrentUsageUseCase, GetUsageReportUseCase
from .config import Settings
from .infrastructure.google.location import GoogleLocationResolver
from .infrastructure.postgres.export_service import ExportService
from .infrastructure.postgres.import_history import ImportHistoryReader


@dataclass(frozen=True, slots=True)
class AppContainer:
    settings: Settings
    search_google_places: SearchGooglePlacesUseCase
    get_map_snapshot: GetMapSnapshotUseCase
    location_resolver: GoogleLocationResolver | None = None
    metrics: MetricsRecorder = field(default_factory=NullMetricsRecorder)
    metrics_exporter: object | None = None
    readiness: CheckReadinessUseCase = field(default_factory=CheckReadinessUseCase)
    login: LoginUseCase | None = None
    get_current_session: GetCurrentSessionUseCase | None = None
    logout: LogoutUseCase | None = None
    create_organization: CreateOrganizationUseCase | None = None
    list_platform_organizations: ListPlatformOrganizationsUseCase | None = None
    suspend_organization: ChangeOrganizationStatusUseCase | None = None
    reactivate_organization: ChangeOrganizationStatusUseCase | None = None
    list_tenant_audit_events: ListTenantAuditEventsUseCase | None = None
    list_platform_audit_events: ListPlatformAuditEventsUseCase | None = None
    get_dashboard_summary: GetDashboardSummaryUseCase | None = None
    get_usage_report: GetUsageReportUseCase | None = None
    get_current_usage: GetCurrentUsageUseCase | None = None
    usage_store: UsageStore | None = None
    create_manual_prospect: CreateManualProspectUseCase | None = None
    add_google_prospects: AddGoogleProspectsUseCase | None = None
    list_prospects: ListProspectsUseCase | None = None
    get_prospect: GetProspectUseCase | None = None
    update_prospect_profile: UpdateProspectProfileUseCase | None = None
    create_activity: CreateActivityUseCase | None = None
    create_task: CreateTaskUseCase | None = None
    create_opportunity: CreateOpportunityUseCase | None = None
    update_opportunity: UpdateOpportunityUseCase | None = None
    transition_opportunity: TransitionOpportunityUseCase | None = None
    reopen_opportunity: ReopenOpportunityUseCase | None = None
    get_opportunity: GetOpportunityUseCase | None = None
    list_opportunities: ListOpportunitiesUseCase | None = None
    list_opportunity_events: ListOpportunityEventsUseCase | None = None
    list_opportunity_summaries: ListOpportunitySummariesUseCase | None = None
    update_task: UpdateTaskUseCase | None = None
    list_prospect_timeline: ListProspectTimelineUseCase | None = None
    list_tasks: ListTasksUseCase | None = None
    list_due_reminders: ListDueRemindersUseCase | None = None
    list_next_actions: ListNextActionsUseCase | None = None
    list_pipeline_stages: ListPipelineStagesUseCase | None = None
    get_pipeline_board: GetPipelineBoardUseCase | None = None
    list_pipeline_column: ListPipelineColumnUseCase | None = None
    move_prospect_stage: MoveProspectStageUseCase | None = None
    reopen_prospect: ReopenProspectUseCase | None = None
    list_prospect_stage_transitions: ListProspectStageTransitionsUseCase | None = None
    update_pipeline_stage: UpdatePipelineStageUseCase | None = None
    create_source_provider: CreateSourceProviderUseCase | None = None
    update_source_provider: UpdateSourceProviderUseCase | None = None
    get_source_provider: GetSourceProviderUseCase | None = None
    list_source_providers: ListSourceProvidersUseCase | None = None
    declare_acquisition: DeclareAcquisitionUseCase | None = None
    get_acquisition: GetAcquisitionUseCase | None = None
    list_acquisitions: ListAcquisitionsUseCase | None = None
    decide_acquisition: DecideAcquisitionUseCase | None = None
    create_contact: CreateContactUseCase | None = None
    list_contacts: ListContactsUseCase | None = None
    list_contact_channels: ListContactChannelsUseCase | None = None
    list_prospect_channels: ListProspectChannelsUseCase | None = None
    create_contact_channel: CreateContactChannelUseCase | None = None
    get_contact_permission: GetContactPermissionUseCase | None = None
    change_contact_permission: ChangeContactPermissionUseCase | None = None
    create_retention_policy: CreateRetentionPolicyUseCase | None = None
    update_retention_policy: UpdateRetentionPolicyUseCase | None = None
    activate_retention_policy: ActivateRetentionPolicyUseCase | None = None
    list_retention_policies: ListRetentionPoliciesUseCase | None = None
    get_retention_policy: GetRetentionPolicyUseCase | None = None
    list_retention_reviews: ListRetentionReviewsUseCase | None = None
    place_retention_hold: PlaceRetentionHoldUseCase | None = None
    list_retention_holds: ListRetentionHoldsUseCase | None = None
    get_retention_hold: GetRetentionHoldUseCase | None = None
    release_retention_hold: ReleaseRetentionHoldUseCase | None = None
    declare_import: DeclareImportUseCase | None = None
    list_import_declarations: ListImportDeclarationsUseCase | None = None
    get_import_declaration: GetImportDeclarationUseCase | None = None
    cancel_import_declaration: CancelImportDeclarationUseCase | None = None
    archive_import_declaration: ArchiveImportDeclarationUseCase | None = None
    upload_csv_import: UploadCsvImportUseCase | None = None
    get_csv_import_preview: GetCsvImportPreviewUseCase | None = None
    map_csv_import: MapCsvImportUseCase | None = None
    validate_csv_import: ValidateCsvImportUseCase | None = None
    confirm_csv_import: ConfirmCsvImportUseCase | None = None
    get_csv_import_report: GetCsvImportReportUseCase | None = None
    csv_import_file_store: TemporaryCsvFileStore | None = None
    import_history: ImportHistoryReader | None = None
    exports: ExportService | None = None
    archive_prospect: ArchiveProspectUseCase | None = None
    archive_contact: ArchiveContactUseCase | None = None
    archive_contact_channel: ArchiveContactChannelUseCase | None = None
    resend_initial_invitation: ResendInitialInvitationUseCase | None = None
    revoke_initial_invitation: RevokeInitialInvitationUseCase | None = None
    preview_invitation: PreviewInvitationUseCase | None = None
    accept_invitation: AcceptInvitationUseCase | None = None
    get_organization: GetOrganizationUseCase | None = None
    update_organization: UpdateOrganizationUseCase | None = None
    list_members: ListMembersUseCase | None = None
    update_membership: UpdateMembershipUseCase | None = None
    list_member_invitations: ListMemberInvitationsUseCase | None = None
    create_member_invitation: CreateMemberInvitationUseCase | None = None
    resend_member_invitation: ResendMemberInvitationUseCase | None = None
    revoke_member_invitation: RevokeMemberInvitationUseCase | None = None
    switch_organization: SwitchOrganizationUseCase | None = None
    unit_of_work_factory: UnitOfWorkFactory | None = None
    tenant_unit_of_work_factory: TenantUnitOfWorkFactory | None = None
    resources: tuple[AsyncResource, ...] = ()

    async def close(self) -> None:
        errors: list[Exception] = []
        for resource in reversed(self.resources):
            try:
                await resource.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("La fermeture des ressources applicatives a échoué.", errors)
