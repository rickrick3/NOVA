"""Composition root: the only place that wires modules together."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nova_core import __version__
from nova_core.audit.service import AuditService
from nova_core.identity import api as identity_api
from nova_core.kernel import api as system_api
from nova_core.kernel import db, migrate
from nova_core.kernel.clock import Clock, SystemClock
from nova_core.kernel.config import Settings
from nova_core.kernel.errors import install_error_handlers
from nova_core.kernel.http_guards import HostOriginMiddleware
from nova_core.kernel.logging import RequestContextMiddleware
from nova_core.kernel.ratelimit import TokenBucketLimiter
from nova_core.projects import api as projects_api
from nova_core.projects.service import ProjectService
from nova_core.storage.service import BlobService

API_PREFIX = "/api/v1"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    database_url = settings.resolved_database_url
    # Alembic is synchronous and must not run on the event loop.
    await asyncio.to_thread(migrate.upgrade, database_url)

    engine = db.create_engine(database_url)
    app.state.engine = engine
    app.state.session_factory = db.create_session_factory(engine)
    try:
        async with app.state.session_factory() as session:
            # Before any request is served: drop files left behind by rolled-back writes.
            await BlobService(
                session, settings.data_dir / "blobs", app.state.clock, settings.max_blob_bytes
            ).collect_garbage()
            clock = app.state.clock
            await ProjectService(session, AuditService(session, clock), clock).ensure_default()
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None, *, clock: Clock | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="NOVA Core",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    auth_refill = settings.auth_rate_limit_attempts / settings.auth_rate_limit_window_seconds
    app.state.rate_limiters = {
        name: TokenBucketLimiter(settings.auth_rate_limit_attempts, auth_refill, app.state.clock)
        for name in ("auth.setup", "auth.login")
    }

    install_error_handlers(app)
    # The middleware added last runs first: the request gets its identifier, then the
    # Host and Origin checks apply, before any route.
    app.add_middleware(
        HostOriginMiddleware,
        allowed_hosts=settings.allowed_hosts,
        allowed_origins=settings.allowed_origins,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(system_api.router, prefix=API_PREFIX)
    app.include_router(identity_api.router, prefix=API_PREFIX)
    app.include_router(projects_api.router, prefix=API_PREFIX)
    return app
