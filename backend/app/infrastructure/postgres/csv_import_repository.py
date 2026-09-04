from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.ports.prospect import CsvImportRepository
from ...domain.csv_import import CsvImportQuarantineView, CsvImportRunView, CsvImportSessionView, CsvImportStatus


class SqlAlchemyCsvImportRepository(CsvImportRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_session(
        self,
        *,
        declaration_id: UUID,
        file_ref: str,
        content_sha256: str,
        byte_size: int,
        headers: tuple[str, ...],
        now: datetime,
        expires_at: datetime,
    ) -> CsvImportSessionView:
        row = (
            (
                await self._session.execute(
                    text("""
            INSERT INTO public.csv_import_sessions (
                id, organization_id, declaration_id, file_ref, content_sha256, byte_size, headers,
                mapping, status, ready_count, duplicate_count, review_count, quarantined_count,
                created_at, expires_at, version
            ) VALUES (
                :id, app_private.current_organization_id(), :declaration_id, :file_ref, :content_sha256,
                :byte_size, CAST(:headers AS jsonb), '{}'::jsonb, 'uploaded', 0, 0, 0, 0, :now, :expires_at, 1
            ) RETURNING *
        """),
                    {
                        "id": uuid4(),
                        "declaration_id": declaration_id,
                        "file_ref": file_ref,
                        "content_sha256": content_sha256,
                        "byte_size": byte_size,
                        "headers": json.dumps(headers),
                        "now": now,
                        "expires_at": expires_at,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _session_from_row(cast(Mapping[str, object], row))

    async def get_session(self, session_id: UUID) -> CsvImportSessionView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.csv_import_sessions WHERE id = :id"), {"id": session_id}
                )
            )
            .mappings()
            .one_or_none()
        )
        return _session_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def update_mapping(
        self, session_id: UUID, *, expected_version: int, mapping: dict[str, str], now: datetime
    ) -> CsvImportSessionView | None:
        row = (
            (
                await self._session.execute(
                    text("""
            UPDATE public.csv_import_sessions
            SET mapping = CAST(:mapping AS jsonb), status = 'mapped', updated_at = :now, version = version + 1
            WHERE id = :id AND version = :version AND status IN ('uploaded', 'mapped', 'validated') AND expires_at > :now
            RETURNING *
        """),
                    {"id": session_id, "version": expected_version, "mapping": json.dumps(mapping), "now": now},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _session_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def record_validation(
        self,
        session_id: UUID,
        *,
        expected_version: int,
        row_count: int,
        ready_count: int,
        duplicate_count: int,
        review_count: int,
        quarantined_count: int,
        now: datetime,
    ) -> CsvImportSessionView | None:
        row = (
            (
                await self._session.execute(
                    text("""
            UPDATE public.csv_import_sessions
            SET status = 'validated', row_count = :row_count, ready_count = :ready_count,
                duplicate_count = :duplicate_count, review_count = :review_count,
                quarantined_count = :quarantined_count, updated_at = :now, version = version + 1
            WHERE id = :id AND version = :version AND status IN ('mapped', 'validated') AND expires_at > :now
            RETURNING *
        """),
                    {
                        "id": session_id,
                        "version": expected_version,
                        "row_count": row_count,
                        "ready_count": ready_count,
                        "duplicate_count": duplicate_count,
                        "review_count": review_count,
                        "quarantined_count": quarantined_count,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        return _session_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def get_run_by_idempotency_key(self, idempotency_key: str) -> CsvImportRunView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.csv_import_runs WHERE idempotency_key = :key"), {"key": idempotency_key}
                )
            )
            .mappings()
            .one_or_none()
        )
        return _run_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def get_run(self, run_id: UUID) -> CsvImportRunView | None:
        row = (
            (await self._session.execute(text("SELECT * FROM public.csv_import_runs WHERE id = :id"), {"id": run_id}))
            .mappings()
            .one_or_none()
        )
        return _run_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def add_run(
        self,
        *,
        session_id: UUID,
        idempotency_key: str,
        command_fingerprint: str,
        created_count: int,
        duplicate_count: int,
        review_count: int,
        quarantined_count: int,
        now: datetime,
    ) -> CsvImportRunView:
        row = (
            (
                await self._session.execute(
                    text("""
            INSERT INTO public.csv_import_runs (
                id, organization_id, session_id, idempotency_key, command_fingerprint, created_count,
                duplicate_count, review_count, quarantined_count, completed_at
            ) VALUES (:id, app_private.current_organization_id(), :session_id, :key, :fingerprint,
                :created_count, :duplicate_count, :review_count, :quarantined_count, :now) RETURNING *
        """),
                    {
                        "id": uuid4(),
                        "session_id": session_id,
                        "key": idempotency_key,
                        "fingerprint": command_fingerprint,
                        "created_count": created_count,
                        "duplicate_count": duplicate_count,
                        "review_count": review_count,
                        "quarantined_count": quarantined_count,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _run_from_row(cast(Mapping[str, object], row))

    async def mark_confirmed(
        self, session_id: UUID, *, expected_version: int, now: datetime
    ) -> CsvImportSessionView | None:
        row = (
            (
                await self._session.execute(
                    text("""
            UPDATE public.csv_import_sessions SET status = 'confirmed', confirmed_at = :now, updated_at = :now, version = version + 1
            WHERE id = :id AND version = :version AND status = 'validated' AND expires_at > :now RETURNING *
        """),
                    {"id": session_id, "version": expected_version, "now": now},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _session_from_row(cast(Mapping[str, object], row)) if row is not None else None

    async def add_quarantines(self, *, run_id: UUID, rows: tuple[CsvImportQuarantineView, ...], now: datetime) -> None:
        for item in rows:
            await self._session.execute(
                text("""
                INSERT INTO public.csv_import_quarantines (id, organization_id, run_id, line_number, reason_codes, opaque_reference, created_at)
                VALUES (:id, app_private.current_organization_id(), :run_id, :line_number, CAST(:reason_codes AS jsonb), :opaque_reference, :now)
            """),
                {
                    "id": uuid4(),
                    "run_id": run_id,
                    "line_number": item.line_number,
                    "reason_codes": json.dumps(item.reason_codes),
                    "opaque_reference": item.opaque_reference,
                    "now": now,
                },
            )

    async def list_quarantines(self, run_id: UUID, *, limit: int) -> tuple[CsvImportQuarantineView, ...]:
        rows = (
            (
                await self._session.execute(
                    text("""
            SELECT line_number, reason_codes, opaque_reference FROM public.csv_import_quarantines
            WHERE run_id = :run_id ORDER BY line_number ASC LIMIT :limit
        """),
                    {"run_id": run_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(
            CsvImportQuarantineView(
                line_number=int(row["line_number"]),
                reason_codes=tuple(cast(list[str], row["reason_codes"])),
                opaque_reference=str(row["opaque_reference"]),
            )
            for row in rows
        )

    async def fingerprint_exists(self, fingerprint: str) -> bool:
        return bool(
            (
                await self._session.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM public.csv_import_fingerprints WHERE fingerprint = :fingerprint)"
                    ),
                    {"fingerprint": fingerprint},
                )
            ).scalar_one()
        )

    async def add_fingerprint(self, *, fingerprint: str, prospect_id: UUID, now: datetime) -> None:
        await self._session.execute(
            text("""
            INSERT INTO public.csv_import_fingerprints (organization_id, fingerprint, prospect_id, created_at)
            VALUES (app_private.current_organization_id(), :fingerprint, :prospect_id, :now)
            ON CONFLICT (organization_id, fingerprint) DO NOTHING
        """),
            {"fingerprint": fingerprint, "prospect_id": prospect_id, "now": now},
        )


def _session_from_row(row: Mapping[str, object]) -> CsvImportSessionView:
    return CsvImportSessionView(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        declaration_id=cast(UUID, row["declaration_id"]),
        file_ref=str(row["file_ref"]),
        content_sha256=str(row["content_sha256"]),
        byte_size=cast(int, row["byte_size"]),
        headers=tuple(cast(list[str], row["headers"])),
        mapping=dict(cast(dict[str, str], row["mapping"])),
        status=CsvImportStatus(str(row["status"])),
        row_count=cast(int | None, row["row_count"]),
        ready_count=cast(int, row["ready_count"]),
        duplicate_count=cast(int, row["duplicate_count"]),
        review_count=cast(int, row["review_count"]),
        quarantined_count=cast(int, row["quarantined_count"]),
        created_at=cast(datetime, row["created_at"]),
        expires_at=cast(datetime, row["expires_at"]),
        confirmed_at=cast(datetime | None, row["confirmed_at"]),
        version=cast(int, row["version"]),
    )


def _run_from_row(row: Mapping[str, object]) -> CsvImportRunView:
    return CsvImportRunView(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        session_id=cast(UUID, row["session_id"]),
        idempotency_key=str(row["idempotency_key"]),
        command_fingerprint=str(row["command_fingerprint"]),
        created_count=cast(int, row["created_count"]),
        duplicate_count=cast(int, row["duplicate_count"]),
        review_count=cast(int, row["review_count"]),
        quarantined_count=cast(int, row["quarantined_count"]),
        completed_at=cast(datetime, row["completed_at"]),
    )
