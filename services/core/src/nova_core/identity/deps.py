"""FastAPI dependencies other modules use to require an authenticated user."""

import hmac
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.audit.service import AuditService
from nova_core.identity.service import IdentityService, SessionContext
from nova_core.kernel.db import get_session
from nova_core.kernel.errors import NovaError
from nova_core.kernel.http_guards import SAFE_METHODS

DbSession = Annotated[AsyncSession, Depends(get_session)]


def get_identity_service(request: Request, session: DbSession) -> IdentityService:
    state = request.app.state
    return IdentityService(session, AuditService(session, state.clock), state.clock, state.settings)


IdentityDep = Annotated[IdentityService, Depends(get_identity_service)]


async def current_session(request: Request, identity: IdentityService) -> SessionContext | None:
    token = request.cookies.get(request.app.state.settings.session_cookie_name)
    return await identity.authenticate(token) if token else None


async def require_session(request: Request, identity: IdentityDep) -> SessionContext:
    context = await current_session(request, identity)
    if context is None:
        raise NovaError("not_authenticated", 401, "Authentication is required.")
    if request.method not in SAFE_METHODS:
        supplied = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(supplied.encode(), context.csrf_token.encode()):
            raise NovaError("csrf_failed", 403, "Missing or invalid CSRF token.")
    return context


CurrentSession = Annotated[SessionContext, Depends(require_session)]
