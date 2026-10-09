from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from nova_core import __version__

router = APIRouter(prefix="/system", tags=["system"])


class Health(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health")
async def health() -> Health:
    return Health(status="ok", version=__version__)
