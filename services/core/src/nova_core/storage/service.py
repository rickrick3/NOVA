"""Content-addressed blob store.

A collaborator service: ``put`` and ``release`` never commit, the caller does.
Files are written before the row is committed, so a rolled-back ``put`` can leave a file
without a row; ``collect_garbage`` removes those.
"""

import asyncio
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.kernel.clock import Clock
from nova_core.kernel.errors import NovaError
from nova_core.kernel.ids import new_id
from nova_core.storage.repository import BlobRepository

_KEY = re.compile(r"[0-9a-f]{64}")
_logger = logging.getLogger("nova_core.storage")


@dataclass(frozen=True)
class BlobRef:
    sha256: str
    size: int
    media_type: str


class BlobNotFoundError(NovaError):
    def __init__(self) -> None:
        super().__init__("not_found", 404, "Stored file not found.")


class BlobTooLargeError(NovaError):
    def __init__(self, size: int, limit: int) -> None:
        super().__init__(
            "validation_error", 422, f"Content is {size} bytes; the limit is {limit} bytes."
        )


def _write_if_absent(path: Path, data: bytes) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{new_id()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _remove_files_without_row(root: Path, known: set[str], min_age_seconds: float) -> int:
    removed = 0
    if not root.is_dir():
        return removed
    # File ages come from the file system, so they are compared with the system time.
    newest_removable = time.time() - min_age_seconds
    for path in root.rglob("*"):
        try:
            if not path.is_file() or not _KEY.fullmatch(path.name) or path.name in known:
                continue
            if min_age_seconds > 0 and path.stat().st_mtime > newest_removable:
                continue
            path.unlink()
            removed += 1
        except OSError:
            # One file that cannot be removed must not stop the Core from starting.
            _logger.warning("could not remove an unreferenced stored file", exc_info=True)
    return removed


class BlobService:
    def __init__(self, session: AsyncSession, root: Path, clock: Clock, max_bytes: int) -> None:
        self.root = root
        self._session = session
        self._blobs = BlobRepository(session)
        self._clock = clock
        self._max_bytes = max_bytes

    def _path(self, sha256: str) -> Path:
        # The key becomes a path: anything but 64 lowercase hex digits is refused outright.
        if not _KEY.fullmatch(sha256):
            raise ValueError("a blob key is 64 lowercase hexadecimal digits")
        return self.root / sha256[0:2] / sha256[2:4] / sha256

    async def put(self, data: bytes, media_type: str) -> BlobRef:
        if len(data) > self._max_bytes:
            raise BlobTooLargeError(len(data), self._max_bytes)
        sha256 = hashlib.sha256(data).hexdigest()
        await asyncio.to_thread(_write_if_absent, self._path(sha256), data)
        await self._blobs.add_reference(
            sha256, size=len(data), media_type=media_type, created_at=self._clock.now()
        )
        blob = await self._blobs.current(sha256)
        if blob is None:  # pragma: no cover - the statement above just wrote it
            raise BlobNotFoundError()
        return BlobRef(sha256=blob.sha256, size=blob.size, media_type=blob.media_type)

    async def open(self, sha256: str) -> bytes:
        path = self._path(sha256)
        if await self._blobs.current(sha256) is None:
            raise BlobNotFoundError()
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            raise BlobNotFoundError() from None

    async def release(self, sha256: str) -> None:
        self._path(sha256)
        blob = await self._blobs.current(sha256)
        if blob is None:
            raise BlobNotFoundError()
        await self._blobs.drop_reference(blob)
        if blob.ref_count <= 0:
            await self._blobs.delete(blob)
            await self._session.flush()

    async def collect_garbage(self, *, min_age_seconds: float = 0.0) -> int:
        """Deletes stored files that no row references and returns how many.

        A file written by a ``put`` that has not committed yet looks unreferenced. Callers
        that may run next to a writer (the startup of a second process, for instance) pass
        a grace period: files younger than ``min_age_seconds`` are left alone.
        """
        known = await self._blobs.keys()
        return await asyncio.to_thread(_remove_files_without_row, self.root, known, min_age_seconds)
