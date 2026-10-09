from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.storage.models import Blob


class BlobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def current(self, sha256: str) -> Blob | None:
        """The row as the database has it now, not as this session last saw it."""
        return await self._session.get(Blob, sha256, populate_existing=True)

    async def add_reference(
        self, sha256: str, *, size: int, media_type: str, created_at: datetime
    ) -> None:
        """Inserts the row with one reference, or adds one reference to the existing row.

        A single statement: two writers that both believe they are first cannot lose a count.
        """
        dialect = self._session.get_bind().dialect.name
        insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
        statement = insert(Blob).values(
            sha256=sha256, size=size, media_type=media_type, ref_count=1, created_at=created_at
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[Blob.sha256], set_={"ref_count": Blob.ref_count + 1}
            )
        )

    async def drop_reference(self, blob: Blob) -> None:
        # The decrement is computed by the database, not from the value this session read.
        blob.ref_count = Blob.ref_count - 1
        await self._session.flush()
        await self._session.refresh(blob)

    async def delete(self, blob: Blob) -> None:
        await self._session.delete(blob)

    async def keys(self) -> set[str]:
        return set((await self._session.execute(select(Blob.sha256))).scalars())
