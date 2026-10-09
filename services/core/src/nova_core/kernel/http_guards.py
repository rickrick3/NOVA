"""Host and Origin checks applied to every request.

The Host check defeats DNS rebinding, which matters even on a loopback-only server: a web
page the user visits could otherwise reach the local API under its own hostname.
"""

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from nova_core.kernel.errors import problem

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class HostOriginMiddleware:
    def __init__(
        self, app: ASGIApp, *, allowed_hosts: frozenset[str], allowed_origins: frozenset[str]
    ) -> None:
        self.app = app
        self._allowed_hosts = allowed_hosts
        self._allowed_origins = allowed_origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        refusal: tuple[str, str] | None = None
        host = headers.get("host")
        if host is None or host.lower() not in self._allowed_hosts:
            refusal = ("host_not_allowed", "This host is not allowed.")
        elif scope["method"] not in SAFE_METHODS:
            # An absent Origin is accepted: non-browser clients do not send one, and
            # session routes are protected by the CSRF token anyway.
            origin = headers.get("origin")
            if origin is not None and origin not in self._allowed_origins:
                refusal = ("csrf_failed", "This origin is not allowed.")

        if refusal is None:
            await self.app(scope, receive, send)
            return
        code, detail = refusal
        request_id = scope.get("state", {}).get("request_id")
        await problem(status=403, code=code, detail=detail, request_id=request_id)(
            scope, receive, send
        )
