from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("scope IN ('tenant', 'platform')", name="scope_allowed"),
        CheckConstraint("scope <> 'tenant' OR organization_id IS NOT NULL", name="tenant_has_organization"),
        CheckConstraint("actor_kind IN ('user', 'system')", name="actor_kind_allowed"),
        CheckConstraint("actor_kind <> 'user' OR actor_id IS NOT NULL", name="user_has_actor"),
        CheckConstraint("actor_kind <> 'system' OR actor_id IS NULL", name="system_has_no_actor"),
        CheckConstraint(
            "action ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'",
            name="action_format",
        ),
        CheckConstraint("entity_type ~ '^[a-z][a-z0-9_]{0,63}$'", name="entity_type_format"),
        CheckConstraint(
            "char_length(request_id) BETWEEN 1 AND 128 AND request_id !~ '[[:cntrl:]]'",
            name="request_id_format",
        ),
        CheckConstraint(
            "char_length(correlation_id) BETWEEN 1 AND 128 AND correlation_id !~ '[[:cntrl:]]'",
            name="correlation_id_format",
        ),
        CheckConstraint("source IN ('api', 'cli', 'worker')", name="source_allowed"),
        CheckConstraint(
            "jsonb_typeof(metadata) = 'object' AND octet_length(metadata::text) <= 8192",
            name="metadata_object_size",
        ),
        CheckConstraint("schema_version > 0", name="schema_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(16))
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(96))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID | None] = mapped_column()
    request_id: Mapped[str] = mapped_column(String(128))
    correlation_id: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(16))
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    schema_version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


Index(
    "ix_audit_events_scope_organization_occurred_id",
    AuditEventModel.scope,
    AuditEventModel.organization_id,
    AuditEventModel.occurred_at.desc(),
    AuditEventModel.id.desc(),
)
Index(
    "ix_audit_events_scope_organization_entity_occurred_id",
    AuditEventModel.scope,
    AuditEventModel.organization_id,
    AuditEventModel.entity_type,
    AuditEventModel.entity_id,
    AuditEventModel.occurred_at.desc(),
    AuditEventModel.id.desc(),
)
Index(
    "ix_audit_events_scope_actor_occurred_id",
    AuditEventModel.scope,
    AuditEventModel.actor_id,
    AuditEventModel.occurred_at.desc(),
    AuditEventModel.id.desc(),
)
Index("ix_audit_events_request_id", AuditEventModel.request_id)
Index(
    "ix_audit_events_platform_occurred_id",
    AuditEventModel.occurred_at.desc(),
    AuditEventModel.id.desc(),
    postgresql_where=AuditEventModel.scope == "platform",
)
