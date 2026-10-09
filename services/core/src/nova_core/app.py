"""Composition root: the only place that wires modules together."""

from fastapi import FastAPI

from nova_core import __version__
from nova_core.kernel import api as system_api
from nova_core.kernel.clock import Clock, SystemClock
from nova_core.kernel.config import Settings
from nova_core.kernel.errors import install_error_handlers
from nova_core.kernel.logging import RequestContextMiddleware

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None, *, clock: Clock | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="NOVA Core",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.clock = clock or SystemClock()

    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(system_api.router, prefix=API_PREFIX)
    return app
