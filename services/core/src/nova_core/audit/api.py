from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from nova_core.audit.schemas import ActorType, AuditEventOut, AuditEventPage
from nova_core.audit.service import AuditService
from nova_core.kernel.db import DbSession


def build_router(require_auth: Callable[..., Any]) -> APIRouter:
    """Read-only by construction: the only route is a GET (INV-8).

    ``require_auth`` is injected by the composition root so that the audit module keeps
    depending on nothing but the kernel.
    """
    router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_auth)])

    @router.get("")
    async def list_audit_events(
        request: Request,
        session: DbSession,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        cursor: str | None = None,
        action: str | None = None,
        actor_type: ActorType | None = None,
    ) -> AuditEventPage:
        page = await AuditService(session, request.app.state.clock).list(
            limit=limit, cursor=cursor, action=action, actor_type=actor_type
        )
        return AuditEventPage(
            items=[AuditEventOut.model_validate(event) for event in page.items],
            next_cursor=page.next_cursor,
        )

    return router
