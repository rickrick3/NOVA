"""Audit log service.

A collaborator service: ``record`` adds the event to the caller's transaction and never
commits, so an action and its trace are saved together or not at all.
"""

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.audit.models import AuditEvent, AuditImmutableError
from nova_core.audit.repository import AuditRepository
from nova_core.audit.schemas import ActorType, AuditDecision, AuditOutcome, PermissionClass
from nova_core.kernel.clock import Clock
from nova_core.kernel.ids import new_id
from nova_core.kernel.pagination import InvalidCursorError, Page, decode_cursor, encode_cursor

__all__ = ["AuditImmutableError", "AuditService"]

# The log holds no file content, no message text and no secret (07-permissions.md §8).
_FORBIDDEN_RESOURCE_KEYS = frozenset({"password", "token", "secret", "api_key", "content", "text"})


class AuditService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._events = AuditRepository(session)
        self._clock = clock

    async def record(
        self,
        *,
        actor_type: ActorType,
        actor_id: str | None,
        action: str,
        outcome: AuditOutcome,
        permission_class: PermissionClass | None = None,
        decision: AuditDecision | None = None,
        resource: Mapping[str, str | int | bool | None] | None = None,
        task_id: str | None = None,
        step_id: str | None = None,
        approval_request_id: str | None = None,
    ) -> AuditEvent:
        forbidden = _FORBIDDEN_RESOURCE_KEYS & {key.lower() for key in resource or {}}
        if forbidden:
            raise ValueError(f"audit resources must not carry {sorted(forbidden)}")
        event = AuditEvent(
            id=new_id(),
            ts=self._clock.now(),
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            permission_class=permission_class,
            decision=decision,
            resource=dict(resource) if resource is not None else None,
            task_id=task_id,
            step_id=step_id,
            approval_request_id=approval_request_id,
            outcome=outcome,
        )
        self._events.add(event)
        await self._session.flush()
        return event

    async def list(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        action: str | None = None,
        actor_type: ActorType | None = None,
    ) -> Page[AuditEvent]:
        before_seq: int | None = None
        if cursor is not None:
            (value,) = decode_cursor(cursor, arity=1)
            if not isinstance(value, int):
                raise InvalidCursorError()
            before_seq = value
        # One extra row tells whether another page exists.
        rows = await self._events.newest_first(
            limit=limit + 1, before_seq=before_seq, action=action, actor_type=actor_type
        )
        items = rows[:limit]
        next_cursor = encode_cursor([items[-1].seq]) if len(rows) > limit else None
        return Page(items=items, next_cursor=next_cursor)
