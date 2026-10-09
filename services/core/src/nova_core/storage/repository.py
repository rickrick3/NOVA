from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.storage.models import Blob


class BlobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, sha256: str) -> Blob | None:
        return await self._session.get(Blob, sha256)

    def add(self, blob: Blob) -> None:
        self._session.add(blob)

    async def delete(self, blob: Blob) -> None:
        await self._session.delete(blob)

    async def keys(self) -> set[str]:
        return set((await self._session.execute(select(Blob.sha256))).scalars())
