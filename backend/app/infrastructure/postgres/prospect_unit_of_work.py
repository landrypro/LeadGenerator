from __future__ import annotations

from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import OrganizationAdministrationUnavailable
from ...application.tenancy import TenantContext
from .audit_recorder import SqlAlchemyAuditRecorder
from .csv_import_repository import SqlAlchemyCsvImportRepository
from .pipeline_repository import SqlAlchemyPipelineRepository
from .prospect_repository import (
    SqlAlchemyAcquisitionRepository,
    SqlAlchemyContactChannelRepository,
    SqlAlchemyContactPermissionRepository,
    SqlAlchemyContactRepository,
    SqlAlchemyImportDeclarationRepository,
    SqlAlchemyProspectRepository,
    SqlAlchemyProvenanceRepository,
    SqlAlchemyRetentionHoldRepository,
    SqlAlchemyRetentionPolicyRepository,
    SqlAlchemyRetentionReviewRepository,
    SqlAlchemySourceProviderRepository,
)
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork


class SqlAlchemyProspectUnitOfWork(SqlAlchemyTenantUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: TenantContext) -> None:
        super().__init__(session_factory, context)
        self.prospects: SqlAlchemyProspectRepository
        self.pipeline: SqlAlchemyPipelineRepository
        self.contacts: SqlAlchemyContactRepository
        self.contact_channels: SqlAlchemyContactChannelRepository
        self.contact_permissions: SqlAlchemyContactPermissionRepository
        self.provenance: SqlAlchemyProvenanceRepository
        self.source_providers: SqlAlchemySourceProviderRepository
        self.acquisitions: SqlAlchemyAcquisitionRepository
        self.retention_policies: SqlAlchemyRetentionPolicyRepository
        self.retention_reviews: SqlAlchemyRetentionReviewRepository
        self.retention_holds: SqlAlchemyRetentionHoldRepository
        self.import_declarations: SqlAlchemyImportDeclarationRepository
        self.csv_imports: SqlAlchemyCsvImportRepository
        self.audit: SqlAlchemyAuditRecorder

    async def __aenter__(self) -> SqlAlchemyProspectUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        self.prospects = SqlAlchemyProspectRepository(self.session)
        self.pipeline = SqlAlchemyPipelineRepository(self.session)
        self.contacts = SqlAlchemyContactRepository(self.session)
        self.contact_channels = SqlAlchemyContactChannelRepository(self.session)
        self.contact_permissions = SqlAlchemyContactPermissionRepository(self.session)
        self.provenance = SqlAlchemyProvenanceRepository(self.session)
        self.source_providers = SqlAlchemySourceProviderRepository(self.session)
        self.acquisitions = SqlAlchemyAcquisitionRepository(self.session)
        self.retention_policies = SqlAlchemyRetentionPolicyRepository(self.session)
        self.retention_reviews = SqlAlchemyRetentionReviewRepository(self.session)
        self.retention_holds = SqlAlchemyRetentionHoldRepository(self.session)
        self.import_declarations = SqlAlchemyImportDeclarationRepository(self.session)
        self.csv_imports = SqlAlchemyCsvImportRepository(self.session)
        self.audit = SqlAlchemyAuditRecorder(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise OrganizationAdministrationUnavailable from exc_value
