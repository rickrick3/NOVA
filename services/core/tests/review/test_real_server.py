"""Findings of the whole-branch review that only show with the real server wiring."""

import httpx
import uvicorn

from nova_core.__main__ import server_options
from nova_core.app import create_app
from nova_core.kernel.config import Settings
from tests.support import BASE_URL, CREDS


async def test_forwarded_headers_cannot_reset_the_login_rate_limit(settings, clock):
    app = create_app(settings, clock=clock)
    # Same stack as `python -m nova_core`: uvicorn may wrap the app in its proxy middleware.
    config = uvicorn.Config(app, **server_options(settings))
    config.load()
    bad = {**CREDS, "password": "definitely not it"}
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=config.loaded_app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
            await c.post("/api/v1/auth/setup", json=CREDS)
            statuses = [
                (
                    await c.post(
                        "/api/v1/auth/login", json=bad, headers={"X-Forwarded-For": f"10.0.0.{i}"}
                    )
                ).status_code
                for i in range(8)
            ]
    assert statuses == [401] * 5 + [429] * 3


async def test_interactive_docs_are_off_by_default(client):
    for path in ("/api/v1/docs", "/docs", "/docs/oauth2-redirect", "/redoc"):
        assert (await client.get(path)).status_code == 404, path
    assert (await client.get("/api/v1/openapi.json")).status_code == 200


async def test_interactive_docs_can_be_enabled_for_development(tmp_path, clock):
    settings = Settings(_env_file=None, env="test", data_dir=tmp_path / "data", api_docs=True)
    app = create_app(settings, clock=clock)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE_URL
        ) as c:
            assert (await c.get("/api/v1/docs")).status_code == 200
            assert (await c.get("/docs/oauth2-redirect")).status_code == 404


def test_limiter_memory_is_bounded():
    from nova_core.kernel.ratelimit import TokenBucketLimiter
    from tests.support import FakeClock

    limiter = TokenBucketLimiter(capacity=1, refill_per_second=1.0, clock=FakeClock(), max_keys=3)
    for i in range(10):
        limiter.check(f"client-{i}")
    assert limiter.tracked_keys <= 3
