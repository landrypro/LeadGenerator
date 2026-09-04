from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import AsyncIterator
from pathlib import Path
from secrets import token_urlsafe


class LocalTemporaryCsvFileStore:
    """Filesystem adapter for development and a private mounted volume in staging.

    The generated reference is opaque and is never returned as a filesystem path.
    """

    def __init__(self, directory: str, *, max_bytes: int) -> None:
        self._directory = Path(directory)
        self._max_bytes = max_bytes

    async def save(self, chunks: AsyncIterator[bytes]) -> tuple[str, str, int]:
        self._directory.mkdir(parents=True, exist_ok=True)
        reference = token_urlsafe(24)
        destination = self._directory / f"{reference}.csv"
        digest = hashlib.sha256()
        size = 0
        try:
            with destination.open("xb") as handle:
                async for chunk in chunks:
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise ValueError("Le fichier CSV dépasse la limite autorisée.")
                    digest.update(chunk)
                    handle.write(chunk)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return reference, digest.hexdigest(), size

    async def read(self, file_ref: str) -> bytes | None:
        path = self._path(file_ref)
        if not path.is_file():
            return None
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, file_ref: str) -> None:
        await asyncio.to_thread(self._path(file_ref).unlink, missing_ok=True)

    async def cleanup_expired(self, *, max_age_seconds: int) -> int:
        """Remove only opaque CSV files older than the temporary retention window."""
        return await asyncio.to_thread(self._cleanup_expired, max_age_seconds)

    def _cleanup_expired(self, max_age_seconds: int) -> int:
        if max_age_seconds < 1 or not self._directory.is_dir():
            return 0
        cutoff = time.time() - max_age_seconds
        removed = 0
        for path in self._directory.glob("*.csv"):
            try:
                if path.is_file() and path.stat().st_mtime <= cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                # A failed cleanup must never make an unrelated import unavailable.
                continue
        return removed

    def _path(self, file_ref: str) -> Path:
        if not file_ref or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for character in file_ref
        ):
            raise ValueError("Référence de fichier temporaire invalide.")
        return self._directory / f"{file_ref}.csv"
