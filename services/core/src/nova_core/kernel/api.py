import logging
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from nova_core import __version__
from nova_core.kernel import db

router = APIRouter(prefix="/system", tags=["system"])
_logger = logging.getLogger("nova_core.system")


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "error"]


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
