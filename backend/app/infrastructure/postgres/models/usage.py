from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UsageOperationEventModel(Base):
    __tablename__ = "usage_operation_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "operation_id", "event_kind", name="uq_usage_events_operation_kind"),
        Index(
            "uq_usage_events_terminal",
            "organization_id",
            "operation_id",
            unique=True,
            postgresql_where=text("event_kind IN ('upstream_succeeded','upstream_failed')"),
        ),
        CheckConstraint(
            "usage_code IN ('google.places_text_search.quota','google.places_text_search.request',"
            "'google.places_autocomplete.request','google.places_details.request','google.maps_static.request',"
            "'platform.csv_export','platform.csv_import')",
            name="usage_events_code_allowed",
        ),
        CheckConstraint(
            "event_kind IN ('quota_reserved','quota_rejected','upstream_attempted','upstream_succeeded',"
            "'upstream_failed','export_requested','export_ready','export_failed','export_expired','import_confirmed')",
            name="usage_events_kind_allowed",
        ),
        CheckConstraint(
            "outcome IN ('accepted','rejected','attempted','succeeded','failed','indeterminate','expired')",
            name="usage_events_outcome_allowed",
        ),
        CheckConstraint("unit_count >= 0", name="usage_events_units_nonnegative"),
        CheckConstraint(
            "coalesce(row_count,0) >= 0 AND coalesce(created_count,0) >= 0 "
            "AND coalesce(duplicate_count,0) >= 0 AND coalesce(review_count,0) >= 0 "
            "AND coalesce(quarantined_count,0) >= 0 AND coalesce(omitted_count,0) >= 0 "
            "AND coalesce(byte_count,0) >= 0",
            name="usage_events_counts_nonnegative",
        ),
        CheckConstraint(
            "(user_limit IS NULL OR user_limit > 0) AND "
            "(organization_limit IS NULL OR organization_limit > 0) AND "
            "(warning_threshold_percent IS NULL OR warning_threshold_percent BETWEEN 1 AND 100)",
            name="usage_events_policy_values_valid",
        ),
        CheckConstraint("schema_version = 1", name="usage_events_schema_version"),
        Index("ix_usage_events_org_occurred", "organization_id", "occurred_at"),
        Index("ix_usage_events_org_user_occurred", "organization_id", "actor_user_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_membership_id: Mapped[UUID] = mapped_column(ForeignKey("memberships.id", ondelete="RESTRICT"))
    operation_id: Mapped[UUID] = mapped_column()
    usage_code: Mapped[str] = mapped_column(String(64))
    event_kind: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    unit_count: Mapped[int] = mapped_column(BigInteger, server_default=text("1"))
    policy_code: Mapped[str | None] = mapped_column(String(64))
    user_limit: Mapped[int | None] = mapped_column(Integer)
    organization_limit: Mapped[int | None] = mapped_column(Integer)
    warning_threshold_percent: Mapped[int | None] = mapped_column(Integer)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    created_count: Mapped[int | None] = mapped_column(BigInteger)
    duplicate_count: Mapped[int | None] = mapped_column(BigInteger)
    review_count: Mapped[int | None] = mapped_column(BigInteger)
    quarantined_count: Mapped[int | None] = mapped_column(BigInteger)
    omitted_count: Mapped[int | None] = mapped_column(BigInteger)
    byte_count: Mapped[int | None] = mapped_column(BigInteger)
    schema_version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))


class UsageDailyCounterModel(Base):
    __tablename__ = "usage_daily_counters"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "usage_day",
            "usage_code",
            "event_kind",
            "outcome",
            name="uq_usage_daily_dimensions",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("unit_count >= 0", name="usage_daily_units_nonnegative"),
        CheckConstraint(
            "usage_code IN ('google.places_text_search.quota','google.places_text_search.request',"
            "'google.places_autocomplete.request','google.places_details.request','google.maps_static.request',"
            "'platform.csv_export','platform.csv_import')",
            name="usage_daily_code_allowed",
        ),
        CheckConstraint(
            "event_kind IN ('quota_reserved','quota_rejected','upstream_attempted','upstream_succeeded',"
            "'upstream_failed','export_requested','export_ready','export_failed','export_expired','import_confirmed')",
            name="usage_daily_kind_allowed",
        ),
        CheckConstraint(
            "outcome IN ('accepted','rejected','attempted','succeeded','failed','indeterminate','expired')",
            name="usage_daily_outcome_allowed",
        ),
        CheckConstraint(
            "row_count >= 0 AND created_count >= 0 AND duplicate_count >= 0 AND review_count >= 0 "
            "AND quarantined_count >= 0 AND omitted_count >= 0 AND byte_count >= 0",
            name="usage_daily_counts_nonnegative",
        ),
        Index("ix_usage_daily_org_day", "organization_id", "usage_day"),
        Index("ix_usage_daily_org_user_day", "organization_id", "actor_user_id", "usage_day"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    usage_day: Mapped[date] = mapped_column(Date)
    usage_code: Mapped[str] = mapped_column(String(64))
    event_kind: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(16))
    unit_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    row_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    created_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    duplicate_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    review_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    quarantined_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    omitted_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    byte_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    last_recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
