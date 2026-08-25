from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .application.ports import AsyncResource, DependencyProbe, TenantUnitOfWorkFactory, UnitOfWorkFactory
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
    CreateContactChannelUseCase,
    CreateContactUseCase,
    CreateManualProspectUseCase,
    CreateMemberInvitationUseCase,
    CreateOrganizationUseCase,
    CreateRetentionPolicyUseCase,
    CreateSourceProviderUseCase,
    DecideAcquisitionUseCase,
    DeclareAcquisitionUseCase,
    DeclareImportUseCase,
    GetAcquisitionUseCase,
    GetContactPermissionUseCase,
    GetCurrentSessionUseCase,
    GetImportDeclarationUseCase,
    GetMapSnapshotUseCase,
    GetOrganizationUseCase,
    GetProspectUseCase,
    GetRetentionHoldUseCase,
    GetRetentionPolicyUseCase,
    GetSourceProviderUseCase,
    ListAcquisitionsUseCase,
    ListContactChannelsUseCase,
    ListContactsUseCase,
    ListImportDeclarationsUseCase,
    ListMemberInvitationsUseCase,
    ListMembersUseCase,
    ListPlatformAuditEventsUseCase,
    ListPlatformOrganizationsUseCase,
    ListProspectChannelsUseCase,
    ListProspectsUseCase,
    ListRetentionHoldsUseCase,
    ListRetentionPoliciesUseCase,
    ListRetentionReviewsUseCase,
    ListSourceProvidersUseCase,
    ListTenantAuditEventsUseCase,
    LoginUseCase,
    LogoutUseCase,
    PlaceRetentionHoldUseCase,
    PreviewInvitationUseCase,
    ReleaseRetentionHoldUseCase,
    ResendInitialInvitationUseCase,
    ResendMemberInvitationUseCase,
    RevokeInitialInvitationUseCase,
    RevokeMemberInvitationUseCase,
    SearchGooglePlacesUseCase,
    SwitchOrganizationUseCase,
    UpdateMembershipUseCase,
    UpdateOrganizationUseCase,
    UpdateProspectProfileUseCase,
    UpdateRetentionPolicyUseCase,
    UpdateSourceProviderUseCase,
)
from .config import Settings
from .container import AppContainer
from .infrastructure.audit_pagination import HmacAuditCursorCodec
from .infrastructure.clock import SystemClock
from .infrastructure.google.places import (
    GooglePlacesClient,
    GooglePlacesGateway,
    GooglePlacesSettings,
)
from .infrastructure.google.static_maps import GoogleStaticMapGateway
from .infrastructure.health import UnconfiguredDependencyProbe
from .infrastructure.invitations import (
    DisabledInvitationDelivery,
    MailpitInvitationDelivery,
    SecureInvitationTokenGenerator,
)
from .infrastructure.memory import (
    InMemoryGenerationGuard,
    InMemoryGoogleSelectionGrantStore,
    InMemoryMapSnapshotGrantStore,
)
from .infrastructure.pagination import HmacCursorCodec
from .infrastructure.postgres import (
    PostgresDatabase,
    SqlAlchemyOrganizationAdministrationGateway,
    SqlAlchemyProvisioningGateway,
)
from .infrastructure.redis import RedisInvitationRateLimiter, RedisLoginRateLimiter, RedisResource, RedisSessionStore
from .infrastructure.security import Argon2PasswordHasher
from .presentation.api.responses import api_error
from .presentation.api.routers import (
    audit_router,
    auth_router,
    google_places_router,
    health_router,
    invitations_router,
    maps_router,
    organization_router,
    platform_router,
    prospect_compliance_router,
    prospects_router,
    retention_router,
)

DEVELOPMENT_RATE_LIMIT_KEY = b"prospect-development-only-rate-limit-key"


def build_container(settings: Settings) -> AppContainer:
    probes: list[DependencyProbe] = []
    resources: list[AsyncResource] = []
    unit_of_work_factory: UnitOfWorkFactory | None = None
    tenant_unit_of_work_factory: TenantUnitOfWorkFactory | None = None
    database: PostgresDatabase | None = None
    redis: RedisResource | None = None

    if settings.database_url:
        database = PostgresDatabase(
            settings.database_url,
            connect_timeout_seconds=settings.dependency_connect_timeout_seconds,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout_seconds=settings.database_pool_timeout_seconds,
            statement_timeout_ms=settings.database_statement_timeout_ms,
        )
        probes.append(database)
        resources.append(database)
        unit_of_work_factory = database.unit_of_work
        tenant_unit_of_work_factory = database.tenant_unit_of_work
    else:
        probes.append(UnconfiguredDependencyProbe("postgresql"))

    if settings.redis_url:
        redis = RedisResource(
            settings.redis_url,
            connect_timeout_seconds=settings.dependency_connect_timeout_seconds,
            max_connections=settings.redis_max_connections,
        )
        probes.append(redis)
        resources.append(redis)
    else:
        probes.append(UnconfiguredDependencyProbe("redis"))

    places_client = GooglePlacesClient(
        GooglePlacesSettings(
            api_key=settings.google_maps_api_key,
            timeout_seconds=settings.places_timeout_seconds,
        )
    )
    places_gateway = GooglePlacesGateway(places_client)
    generation_guard = InMemoryGenerationGuard()
    map_grants = InMemoryMapSnapshotGrantStore(
        ttl_seconds=settings.map_grant_ttl_seconds,
        max_grants=settings.map_grant_max_entries,
    )
    selection_grants = InMemoryGoogleSelectionGrantStore(
        ttl_seconds=settings.google_selection_grant_ttl_seconds,
        max_grants=settings.google_selection_grant_max_entries,
    )
    static_maps = GoogleStaticMapGateway(
        api_key=settings.static_maps_api_key,
        timeout_seconds=settings.static_maps_timeout_seconds,
    )

    login: LoginUseCase | None = None
    get_current_session: GetCurrentSessionUseCase | None = None
    logout: LogoutUseCase | None = None
    create_organization: CreateOrganizationUseCase | None = None
    list_platform_organizations: ListPlatformOrganizationsUseCase | None = None
    suspend_organization: ChangeOrganizationStatusUseCase | None = None
    reactivate_organization: ChangeOrganizationStatusUseCase | None = None
    list_tenant_audit_events: ListTenantAuditEventsUseCase | None = None
    list_platform_audit_events: ListPlatformAuditEventsUseCase | None = None
    create_manual_prospect: CreateManualProspectUseCase | None = None
    add_google_prospects: AddGoogleProspectsUseCase | None = None
    list_prospects: ListProspectsUseCase | None = None
    get_prospect: GetProspectUseCase | None = None
    update_prospect_profile: UpdateProspectProfileUseCase | None = None
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
    if database is not None and redis is not None:
        clock = SystemClock()
        rate_limit_key = settings.rate_limit_hmac_key.encode("utf-8") or DEVELOPMENT_RATE_LIMIT_KEY
        cursor_codec = HmacCursorCodec(rate_limit_key)
        audit_cursor_codec = HmacAuditCursorCodec(rate_limit_key)
        prospect_cursor_codec = HmacCursorCodec(rate_limit_key)
        session_store = RedisSessionStore(
            redis.client,
            environment=settings.app_env,
            idle_seconds=settings.session_idle_seconds,
            absolute_seconds=settings.session_absolute_seconds,
        )
        login_rate_limiter = RedisLoginRateLimiter(
            redis.client,
            environment=settings.app_env,
            window_seconds=settings.login_rate_limit_window_seconds,
            pair_limit=settings.login_rate_limit_pair_failures,
            address_limit=settings.login_rate_limit_address_failures,
            hmac_key=rate_limit_key,
        )
        invitation_rate_limiter = RedisInvitationRateLimiter(
            redis.client,
            environment=settings.app_env,
            window_seconds=settings.invitation_attempt_window_seconds,
            address_limit=settings.invitation_attempt_address_max,
            token_limit=settings.invitation_attempt_token_max,
            hmac_key=rate_limit_key,
        )
        provisioning_gateway = SqlAlchemyProvisioningGateway(database)
        organization_gateway = SqlAlchemyOrganizationAdministrationGateway(database)
        token_generator = SecureInvitationTokenGenerator()
        invitation_delivery = (
            MailpitInvitationDelivery(
                host=settings.invitation_smtp_host,
                port=settings.invitation_smtp_port,
                timeout_seconds=settings.invitation_smtp_timeout_seconds,
                from_email=settings.invitation_from_email,
            )
            if settings.invitation_delivery_backend == "mailpit"
            else DisabledInvitationDelivery()
        )
        login = LoginUseCase(
            database.identity_unit_of_work,
            Argon2PasswordHasher(),
            session_store,
            login_rate_limiter,
            clock,
        )
        get_current_session = GetCurrentSessionUseCase(database.identity_unit_of_work, session_store, clock)
        logout = LogoutUseCase(session_store, clock)
        create_organization = CreateOrganizationUseCase(
            provisioning_gateway,
            token_generator,
            invitation_delivery,
            clock,
            public_app_url=settings.public_app_url,
            invitation_ttl_seconds=settings.invitation_ttl_seconds,
            audited_unit_of_work_factory=database.platform_audited_unit_of_work,
        )
        list_platform_organizations = ListPlatformOrganizationsUseCase(provisioning_gateway, clock)
        suspend_organization = ChangeOrganizationStatusUseCase(
            provisioning_gateway,
            clock,
            operation="suspend",
            audited_unit_of_work_factory=database.platform_audited_unit_of_work,
        )
        reactivate_organization = ChangeOrganizationStatusUseCase(
            provisioning_gateway,
            clock,
            operation="reactivate",
            audited_unit_of_work_factory=database.platform_audited_unit_of_work,
        )
        resend_initial_invitation = ResendInitialInvitationUseCase(
            provisioning_gateway,
            token_generator,
            invitation_delivery,
            clock,
            public_app_url=settings.public_app_url,
            invitation_ttl_seconds=settings.invitation_ttl_seconds,
            cooldown_seconds=settings.invitation_resend_cooldown_seconds,
            window_seconds=settings.invitation_resend_window_seconds,
            max_per_window=settings.invitation_resend_max_per_window,
            audited_unit_of_work_factory=database.platform_audited_unit_of_work,
        )
        revoke_initial_invitation = RevokeInitialInvitationUseCase(
            provisioning_gateway, clock, database.platform_audited_unit_of_work
        )
        preview_invitation = PreviewInvitationUseCase(provisioning_gateway, invitation_rate_limiter, clock)
        accept_invitation = AcceptInvitationUseCase(
            provisioning_gateway,
            database.identity_unit_of_work,
            Argon2PasswordHasher(),
            session_store,
            invitation_rate_limiter,
            clock,
            database.invitation_acceptance_unit_of_work,
        )
        get_organization = GetOrganizationUseCase(organization_gateway)
        update_organization = UpdateOrganizationUseCase(
            organization_gateway, clock, database.tenant_audited_unit_of_work
        )
        list_members = ListMembersUseCase(organization_gateway, cursor_codec)
        update_membership = UpdateMembershipUseCase(
            organization_gateway, session_store, clock, database.tenant_audited_unit_of_work
        )
        list_member_invitations = ListMemberInvitationsUseCase(organization_gateway, clock, cursor_codec)
        create_member_invitation = CreateMemberInvitationUseCase(
            organization_gateway,
            token_generator,
            invitation_delivery,
            clock,
            public_app_url=settings.public_app_url,
            invitation_ttl_seconds=settings.invitation_ttl_seconds,
            audited_unit_of_work_factory=database.tenant_audited_unit_of_work,
        )
        resend_member_invitation = ResendMemberInvitationUseCase(
            organization_gateway,
            token_generator,
            invitation_delivery,
            clock,
            public_app_url=settings.public_app_url,
            invitation_ttl_seconds=settings.invitation_ttl_seconds,
            cooldown_seconds=settings.invitation_resend_cooldown_seconds,
            window_seconds=settings.invitation_resend_window_seconds,
            max_per_window=settings.invitation_resend_max_per_window,
            audited_unit_of_work_factory=database.tenant_audited_unit_of_work,
        )
        revoke_member_invitation = RevokeMemberInvitationUseCase(
            organization_gateway, clock, database.tenant_audited_unit_of_work
        )
        switch_organization = SwitchOrganizationUseCase(
            organization_gateway,
            database.identity_unit_of_work,
            session_store,
            clock,
            database.actor_audited_unit_of_work,
        )
        list_tenant_audit_events = ListTenantAuditEventsUseCase(
            database.tenant_audit_read_unit_of_work,
            audit_cursor_codec,
            clock,
        )
        list_platform_audit_events = ListPlatformAuditEventsUseCase(
            database.platform_audit_read_unit_of_work,
            audit_cursor_codec,
            clock,
        )
        create_manual_prospect = CreateManualProspectUseCase(database.tenant_prospect_unit_of_work, clock)
        add_google_prospects = AddGoogleProspectsUseCase(
            database.tenant_prospect_unit_of_work,
            selection_grants,
            clock,
            alias_hmac_key=rate_limit_key,
        )
        list_prospects = ListProspectsUseCase(database.tenant_prospect_unit_of_work, prospect_cursor_codec)
        get_prospect = GetProspectUseCase(database.tenant_prospect_unit_of_work)
        update_prospect_profile = UpdateProspectProfileUseCase(database.tenant_prospect_unit_of_work, clock)
        create_source_provider = CreateSourceProviderUseCase(database.tenant_prospect_unit_of_work, clock)
        update_source_provider = UpdateSourceProviderUseCase(database.tenant_prospect_unit_of_work, clock)
        get_source_provider = GetSourceProviderUseCase(database.tenant_prospect_unit_of_work)
        list_source_providers = ListSourceProvidersUseCase(database.tenant_prospect_unit_of_work)
        declare_acquisition = DeclareAcquisitionUseCase(database.tenant_prospect_unit_of_work, clock)
        get_acquisition = GetAcquisitionUseCase(database.tenant_prospect_unit_of_work)
        list_acquisitions = ListAcquisitionsUseCase(database.tenant_prospect_unit_of_work)
        decide_acquisition = DecideAcquisitionUseCase(database.tenant_prospect_unit_of_work, clock)
        create_contact = CreateContactUseCase(database.tenant_prospect_unit_of_work, clock)
        list_contacts = ListContactsUseCase(database.tenant_prospect_unit_of_work)
        list_contact_channels = ListContactChannelsUseCase(database.tenant_prospect_unit_of_work)
        list_prospect_channels = ListProspectChannelsUseCase(database.tenant_prospect_unit_of_work)
        create_contact_channel = CreateContactChannelUseCase(database.tenant_prospect_unit_of_work, clock)
        get_contact_permission = GetContactPermissionUseCase(database.tenant_prospect_unit_of_work)
        change_contact_permission = ChangeContactPermissionUseCase(database.tenant_prospect_unit_of_work, clock)
        create_retention_policy = CreateRetentionPolicyUseCase(database.tenant_prospect_unit_of_work, clock)
        update_retention_policy = UpdateRetentionPolicyUseCase(database.tenant_prospect_unit_of_work, clock)
        activate_retention_policy = ActivateRetentionPolicyUseCase(database.tenant_prospect_unit_of_work, clock)
        list_retention_policies = ListRetentionPoliciesUseCase(database.tenant_prospect_unit_of_work)
        get_retention_policy = GetRetentionPolicyUseCase(database.tenant_prospect_unit_of_work)
        list_retention_reviews = ListRetentionReviewsUseCase(database.tenant_prospect_unit_of_work)
        place_retention_hold = PlaceRetentionHoldUseCase(database.tenant_prospect_unit_of_work, clock)
        list_retention_holds = ListRetentionHoldsUseCase(database.tenant_prospect_unit_of_work)
        get_retention_hold = GetRetentionHoldUseCase(database.tenant_prospect_unit_of_work)
        release_retention_hold = ReleaseRetentionHoldUseCase(database.tenant_prospect_unit_of_work, clock)
        declare_import = DeclareImportUseCase(database.tenant_prospect_unit_of_work, clock)
        list_import_declarations = ListImportDeclarationsUseCase(database.tenant_prospect_unit_of_work)
        get_import_declaration = GetImportDeclarationUseCase(database.tenant_prospect_unit_of_work)
        cancel_import_declaration = CancelImportDeclarationUseCase(database.tenant_prospect_unit_of_work, clock)
        archive_import_declaration = ArchiveImportDeclarationUseCase(database.tenant_prospect_unit_of_work, clock)
        archive_prospect = ArchiveProspectUseCase(database.tenant_prospect_unit_of_work, clock)
        archive_contact = ArchiveContactUseCase(database.tenant_prospect_unit_of_work, clock)
        archive_contact_channel = ArchiveContactChannelUseCase(database.tenant_prospect_unit_of_work, clock)

    return AppContainer(
        settings=settings,
        search_google_places=SearchGooglePlacesUseCase(
            places_gateway,
            generation_guard,
            map_grants,
            selection_grants,
        ),
        get_map_snapshot=GetMapSnapshotUseCase(map_grants, static_maps),
        readiness=CheckReadinessUseCase(probes),
        login=login,
        get_current_session=get_current_session,
        logout=logout,
        create_organization=create_organization,
        list_platform_organizations=list_platform_organizations,
        suspend_organization=suspend_organization,
        reactivate_organization=reactivate_organization,
        list_tenant_audit_events=list_tenant_audit_events,
        list_platform_audit_events=list_platform_audit_events,
        create_manual_prospect=create_manual_prospect,
        add_google_prospects=add_google_prospects,
        list_prospects=list_prospects,
        get_prospect=get_prospect,
        update_prospect_profile=update_prospect_profile,
        create_source_provider=create_source_provider,
        update_source_provider=update_source_provider,
        get_source_provider=get_source_provider,
        list_source_providers=list_source_providers,
        declare_acquisition=declare_acquisition,
        get_acquisition=get_acquisition,
        list_acquisitions=list_acquisitions,
        decide_acquisition=decide_acquisition,
        create_contact=create_contact,
        list_contacts=list_contacts,
        list_contact_channels=list_contact_channels,
        list_prospect_channels=list_prospect_channels,
        create_contact_channel=create_contact_channel,
        get_contact_permission=get_contact_permission,
        change_contact_permission=change_contact_permission,
        create_retention_policy=create_retention_policy,
        update_retention_policy=update_retention_policy,
        activate_retention_policy=activate_retention_policy,
        list_retention_policies=list_retention_policies,
        get_retention_policy=get_retention_policy,
        list_retention_reviews=list_retention_reviews,
        place_retention_hold=place_retention_hold,
        list_retention_holds=list_retention_holds,
        get_retention_hold=get_retention_hold,
        release_retention_hold=release_retention_hold,
        declare_import=declare_import,
        list_import_declarations=list_import_declarations,
        get_import_declaration=get_import_declaration,
        cancel_import_declaration=cancel_import_declaration,
        archive_import_declaration=archive_import_declaration,
        archive_prospect=archive_prospect,
        archive_contact=archive_contact,
        archive_contact_channel=archive_contact_channel,
        resend_initial_invitation=resend_initial_invitation,
        revoke_initial_invitation=revoke_initial_invitation,
        preview_invitation=preview_invitation,
        accept_invitation=accept_invitation,
        get_organization=get_organization,
        update_organization=update_organization,
        list_members=list_members,
        update_membership=update_membership,
        list_member_invitations=list_member_invitations,
        create_member_invitation=create_member_invitation,
        resend_member_invitation=resend_member_invitation,
        revoke_member_invitation=revoke_member_invitation,
        switch_organization=switch_organization,
        unit_of_work_factory=unit_of_work_factory,
        tenant_unit_of_work_factory=tenant_unit_of_work_factory,
        resources=tuple(resources),
    )


def create_app(
    settings: Settings | None = None,
    container: AppContainer | None = None,
) -> FastAPI:
    if settings is not None and container is not None and settings != container.settings:
        raise ValueError("Le conteneur injecté et create_app() doivent utiliser les mêmes Settings.")
    resolved_settings = settings or (container.settings if container else Settings.from_env())
    resolved_container = container or build_container(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await resolved_container.close()

    app = FastAPI(
        title=resolved_settings.app_title,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    app.state.container = resolved_container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.middleware("http")(_add_request_id)

    @app.exception_handler(RequestValidationError)
    async def sanitized_api_validation_error(request: Request, error: RequestValidationError) -> Response:
        protected_payload = request.url.path.startswith(
            (
                "/api/auth/",
                "/api/google/",
                "/api/map/",
                "/api/audit-events",
                "/api/platform/audit-events",
                "/api/prospects",
                "/api/source-providers",
                "/api/acquisitions",
                "/api/contact-channels",
                "/api/retention",
                "/api/import-declarations",
                "/api/contacts",
            )
        )
        if not protected_payload:
            return await request_validation_exception_handler(request, error)
        if request.url.path.startswith(
            (
                "/api/google/",
                "/api/map/",
                "/api/prospects",
                "/api/source-providers",
                "/api/acquisitions",
                "/api/contact-channels",
                "/api/retention",
                "/api/import-declarations",
                "/api/contacts",
            )
        ):
            content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
            if content_type != "application/json":
                return api_error(
                    request,
                    415,
                    "json_required",
                    "Le type application/json est obligatoire.",
                )
        if request.url.path.startswith("/api/auth/invitations/") and any(
            item.get("loc") and item["loc"][-1] == "token" for item in error.errors()
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "invitation_invalid",
                        "message": "L’invitation n’est pas utilisable.",
                        "request_id": getattr(request.state, "request_id", ""),
                    }
                },
                headers={"Cache-Control": "no-store, max-age=0"},
            )
        fields = {str(item["loc"][-1]): "Valeur invalide." for item in error.errors() if item.get("loc")}
        if request.url.path.startswith(("/api/audit-events", "/api/platform/audit-events")):
            message = "Les filtres d’audit sont invalides."
        elif request.url.path.startswith(("/api/google/", "/api/map/")):
            message = "La commande Google est invalide."
        elif request.url.path.startswith(
            (
                "/api/prospects",
                "/api/source-providers",
                "/api/acquisitions",
                "/api/contact-channels",
                "/api/retention",
                "/api/import-declarations",
                "/api/contacts",
            )
        ):
            message = "La commande prospect est invalide."
        else:
            message = "La requête d’authentification est invalide."
        return api_error(
            request,
            422,
            "validation_failed",
            message,
            fields=fields,
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(invitations_router)
    app.include_router(platform_router)
    app.include_router(organization_router)
    app.include_router(google_places_router)
    app.include_router(prospects_router)
    app.include_router(prospect_compliance_router)
    app.include_router(retention_router)
    app.include_router(maps_router)

    frontend_dist = Path(__file__).resolve().parents[2] / "client" / "dist"
    if frontend_dist.exists():
        assets = frontend_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def frontend_route(frontend_path: str) -> Response:
            if frontend_path.startswith("api/"):
                raise HTTPException(status_code=404)
            candidate = (frontend_dist / frontend_path).resolve()
            if candidate.is_relative_to(frontend_dist.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app


async def _add_request_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    from uuid import uuid4

    request_id = uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
