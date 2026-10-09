import logging
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from nova_core import __version__
from nova_core.kernel import db
from nova_core.kernel.capabilities import CapabilityRegistry, CapabilityState

_logger = logging.getLogger("nova_core.system")


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "error"]


class CapabilityList(BaseModel):
    capabilities: list[CapabilityState]


def build_router(require_auth: Callable[..., Any]) -> APIRouter:
    """``require_auth`` is injected by the composition root: the kernel never imports
    the identity module."""
    router = APIRouter(prefix="/system", tags=["system"])

    @router.get("/health", responses={503: {"model": Health}})
    async def health(request: Request, response: Response) -> Health:
        try:
            # Looked up on the module at call time so a test can replace it.
            await db.ping_database(request.app.state.engine)
        except Exception:
            _logger.exception("database ping failed")
            response.status_code = 503
            return Health(status="degraded", version=__version__, database="error")
        return Health(status="ok", version=__version__, database="ok")

    @router.get("/capabilities", dependencies=[Depends(require_auth)])
    async def capabilities(request: Request) -> CapabilityList:
        registry: CapabilityRegistry = request.app.state.capabilities
        return CapabilityList(capabilities=await registry.snapshot())

    return router
