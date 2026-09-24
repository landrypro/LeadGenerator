from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobModel(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_jobs_organization_id"),
        UniqueConstraint("organization_id", "type", "idempotency_key_digest", name="uq_jobs_idempotency"),
        Index("ix_jobs_claim", "status", "available_at", "created_at"),
        Index("ix_jobs_organization_status", "organization_id", "status"),
        Index("ix_jobs_expiry", "expires_at"),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="status_allowed"),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 3", name="attempts_allowed"
        ),
        CheckConstraint("schema_version > 0 AND version > 0", name="versions_positive"),
        CheckConstraint("(actor_membership_id IS NULL) <> (system_origin IS NULL)", name="origin_exclusive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    type: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(Integer)
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[UUID] = mapped_column()
    replay_of_job_id: Mapped[UUID | None] = mapped_column()
    actor_id: Mapped[UUID] = mapped_column()
    actor_membership_id: Mapped[UUID | None] = mapped_column()
    system_origin: Mapped[str | None] = mapped_column(String(64))
    idempotency_key_digest: Mapped[str] = mapped_column(String(64))
    idempotency_key_version: Mapped[int] = mapped_column(Integer)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_token: Mapped[UUID | None] = mapped_column()
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    result_code: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class JobSchedulerStateModel(Base):
    __tablename__ = "job_scheduler_state"
    __table_args__ = (CheckConstraint("queued_count >= 0 AND active_count BETWEEN 0 AND 1", name="counts_allowed"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    queued_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    active_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobAttemptModel(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="CASCADE"),
        CheckConstraint("attempt_number > 0", name="number_positive"),
    )

    job_id: Mapped[UUID] = mapped_column(primary_key=True)
    attempt_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    owner_token: Mapped[UUID] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_code: Mapped[str | None] = mapped_column(String(64))


class JobEventModel(Base):
    __tablename__ = "job_events"
    __table_args__ = (
        ForeignKeyConstraint(["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="CASCADE"),
        Index("ix_job_events_job_created", "job_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    job_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    old_status: Mapped[str | None] = mapped_column(String(16))
    new_status: Mapped[str] = mapped_column(String(16))
    reason_code: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkerHeartbeatModel(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_cleanup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
