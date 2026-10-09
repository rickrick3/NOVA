"""Content-addressed blob store.

A collaborator service: ``put`` and ``release`` never commit, the caller does.
Files are written before the row is committed, so a rolled-back ``put`` can leave a file
without a row; ``collect_garbage`` removes those.
"""

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.kernel.clock import Clock
from nova_core.kernel.errors import NovaError
from nova_core.kernel.ids import new_id
from nova_core.storage.models import Blob
from nova_core.storage.repository import BlobRepository

_KEY = re.compile(r"[0-9a-f]{64}")


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


def _remove_files_without_row(root: Path, known: set[str]) -> int:
    removed = 0
    if not root.is_dir():
        return removed
    for path in root.rglob("*"):
        if path.is_file() and _KEY.fullmatch(path.name) and path.name not in known:
            path.unlink()
            removed += 1
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

        blob = await self._blobs.get(sha256)
        if blob is None:
            blob = Blob(
                sha256=sha256,
                size=len(data),
                media_type=media_type,
                ref_count=1,
                created_at=self._clock.now(),
            )
            self._blobs.add(blob)
        else:
            blob.ref_count += 1
        # Flushed so that a second put in the same transaction finds the row.
        await self._session.flush()
        return BlobRef(sha256=blob.sha256, size=blob.size, media_type=blob.media_type)

    async def open(self, sha256: str) -> bytes:
        path = self._path(sha256)
        if await self._blobs.get(sha256) is None:
            raise BlobNotFoundError()
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            raise BlobNotFoundError() from None

    async def release(self, sha256: str) -> None:
        self._path(sha256)
        blob = await self._blobs.get(sha256)
        if blob is None:
            raise BlobNotFoundError()
        blob.ref_count -= 1
        if blob.ref_count <= 0:
            await self._blobs.delete(blob)
        await self._session.flush()

    async def collect_garbage(self) -> int:
        """Deletes stored files that no row references and returns how many.

        Must not run while a ``put`` is in flight: a file written but not yet committed
        looks unreferenced. It runs at startup, before any request is served.
        """
        known = await self._blobs.keys()
        return await asyncio.to_thread(_remove_files_without_row, self.root, known)
