from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.audit.models import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, event: AuditEvent) -> None:
        self._session.add(event)

    async def newest_first(
        self,
        *,
        limit: int,
        before_seq: int | None,
        action: str | None,
        actor_type: str | None,
    ) -> list[AuditEvent]:
        statement = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit)
        if before_seq is not None:
            statement = statement.where(AuditEvent.seq < before_seq)
        if action is not None:
            statement = statement.where(AuditEvent.action == action)
        if actor_type is not None:
            statement = statement.where(AuditEvent.actor_type == actor_type)
        return list((await self._session.execute(statement)).scalars())
