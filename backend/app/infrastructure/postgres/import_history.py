"""Minimized, tenant-scoped history of the existing synchronous CSV imports."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.audit_events import tenant_audit_event
from ...application.tenancy import TenantContext
from ...domain.audit import AuditAction
from .audit_recorder import SqlAlchemyAuditRecorder
from .job_queue import _set_tenant


class ImportHistoryReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_sessions(
        self,
        context: TenantContext,
        *,
        limit: int = 25,
        cursor: UUID | None = None,
        status: str | None = None,
        declaration_id: UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        author_id: UUID | None = None,
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            anchor = await self._anchor(session, "csv_import_sessions", "created_at", cursor) if cursor else None
            rows = (
                (
                    await session.execute(
                        text("""
                SELECT s.id, s.declaration_id, s.retry_of_run_id, s.status, s.row_count, s.ready_count,
                       s.duplicate_count, s.review_count, s.quarantined_count, s.created_at,
                       s.expires_at, s.confirmed_at, s.version
                FROM csv_import_sessions s JOIN import_declarations d ON d.id = s.declaration_id
                WHERE (:status IS NULL OR s.status = :status)
                  AND (:declaration_id IS NULL OR s.declaration_id = :declaration_id)
                  AND (:author_id IS NULL OR d.declared_by = :author_id)
                  AND (CAST(:created_from AS timestamptz) IS NULL OR s.created_at >= :created_from)
                  AND (CAST(:created_to AS timestamptz) IS NULL OR s.created_at < :created_to)
                  AND (CAST(:anchor_at AS timestamptz) IS NULL OR (s.created_at, s.id) < (CAST(:anchor_at AS timestamptz), :anchor_id))
                ORDER BY s.created_at DESC, s.id DESC LIMIT :limit
            """),
                        {
                            "status": status,
                            "declaration_id": declaration_id,
                            "created_from": created_from,
                            "created_to": created_to,
                            "author_id": author_id,
                            "anchor_at": anchor[0] if anchor else None,
                            "anchor_id": cursor,
                            "limit": limit + 1,
                        },
                    )
                )
                .mappings()
                .all()
            )
            return _page(rows, limit)

    async def list_runs(
        self,
        context: TenantContext,
        *,
        limit: int = 25,
        cursor: UUID | None = None,
        declaration_id: UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        author_id: UUID | None = None,
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            anchor = await self._anchor(session, "csv_import_runs", "completed_at", cursor) if cursor else None
            rows = (
                (
                    await session.execute(
                        text("""
                SELECT r.id, r.session_id, s.declaration_id, s.retry_of_run_id,
                       r.created_count, r.duplicate_count, r.review_count,
                       r.quarantined_count, r.completed_at
                FROM csv_import_runs r JOIN csv_import_sessions s ON s.id = r.session_id
                JOIN import_declarations d ON d.id = s.declaration_id
                WHERE (:declaration_id IS NULL OR s.declaration_id = :declaration_id)
                  AND (:author_id IS NULL OR d.declared_by = :author_id)
                  AND (CAST(:created_from AS timestamptz) IS NULL OR r.completed_at >= :created_from)
                  AND (CAST(:created_to AS timestamptz) IS NULL OR r.completed_at < :created_to)
                  AND (CAST(:anchor_at AS timestamptz) IS NULL OR (r.completed_at, r.id) < (CAST(:anchor_at AS timestamptz), :anchor_id))
                ORDER BY r.completed_at DESC, r.id DESC LIMIT :limit
            """),
                        {
                            "declaration_id": declaration_id,
                            "created_from": created_from,
                            "created_to": created_to,
                            "author_id": author_id,
                            "anchor_at": anchor[0] if anchor else None,
                            "anchor_id": cursor,
                            "limit": limit + 1,
                        },
                    )
                )
                .mappings()
                .all()
            )
            return _page(rows, limit)

    async def get_session(self, context: TenantContext, session_id: UUID) -> dict[str, Any] | None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            row = (
                (
                    await session.execute(
                        text("""
                SELECT id, declaration_id, retry_of_run_id, content_sha256, byte_size,
                       headers, mapping, status, row_count, ready_count, duplicate_count,
                       review_count, quarantined_count, created_at, expires_at,
                       confirmed_at, version
                FROM csv_import_sessions WHERE id = :id
            """),
                        {"id": session_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            return dict(row) if row else None

    async def get_run(self, context: TenantContext, run_id: UUID) -> dict[str, Any] | None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            row = (
                (
                    await session.execute(
                        text("""
                SELECT r.id, r.session_id, s.declaration_id, s.retry_of_run_id,
                       r.created_count, r.duplicate_count, r.review_count,
                       r.quarantined_count, r.completed_at
                FROM csv_import_runs r JOIN csv_import_sessions s ON s.id = r.session_id
                WHERE r.id = :id
            """),
                        {"id": run_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            await SqlAlchemyAuditRecorder(session).record(
                tenant_audit_event(context, AuditAction.IMPORT_REPORT_VIEWED, run_id)
            )
            return dict(row)

    async def list_quarantines(
        self,
        context: TenantContext,
        run_id: UUID,
        *,
        limit: int = 25,
        after_line: int = 0,
    ) -> dict[str, Any] | None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            exists = (
                await session.execute(text("SELECT 1 FROM csv_import_runs WHERE id = :id"), {"id": run_id})
            ).scalar_one_or_none()
            if exists is None:
                return None
            rows = (
                (
                    await session.execute(
                        text("""
                SELECT line_number, reason_codes, opaque_reference
                FROM csv_import_quarantines
                WHERE run_id = :id AND line_number > :after_line
                ORDER BY line_number LIMIT :limit
            """),
                        {"id": run_id, "after_line": after_line, "limit": limit + 1},
                    )
                )
                .mappings()
                .all()
            )
            await SqlAlchemyAuditRecorder(session).record(
                tenant_audit_event(context, AuditAction.IMPORT_REPORT_VIEWED, run_id, {"kind": "quarantine"})
            )
            items = [dict(row) for row in rows[:limit]]
            return {"items": items, "next_cursor": items[-1]["line_number"] if len(rows) > limit else None}

    @staticmethod
    async def _anchor(session: AsyncSession, table: str, date_field: str, cursor: UUID) -> tuple[datetime]:
        # Identifiers are chosen from a closed set by this class, never from a request.
        value = (
            await session.execute(text(f"SELECT {date_field} FROM {table} WHERE id = :id"), {"id": cursor})
        ).scalar_one_or_none()
        if value is None:
            raise LookupError("Curseur introuvable.")
        return (value,)


def _page(rows: Any, limit: int) -> dict[str, Any]:
    items = [dict(row) for row in rows[:limit]]
    return {"items": items, "next_cursor": str(items[-1]["id"]) if len(rows) > limit else None}
