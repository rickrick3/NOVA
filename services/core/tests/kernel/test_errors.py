import logging

import httpx

from nova_core.kernel.errors import NovaError
from tests.support import BASE_URL


async def test_unknown_route_is_problem_json_with_request_id(client):
    r = await client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert (body["code"], body["status"]) == ("not_found", 404)
    assert body["request_id"] == r.headers["x-request-id"]


async def test_nova_error_carries_code_extra_and_headers(app, client):
    @app.get("/api/v1/_refused")
    async def refused() -> None:
        raise NovaError(
            "protected_resource", 409, "nope", extra={"hint": "x"}, headers={"Retry-After": "7"}
        )

    r = await client.get("/api/v1/_refused")
    assert r.status_code == 409
    assert (r.json()["code"], r.json()["hint"]) == ("protected_resource", "x")
    assert r.headers["retry-after"] == "7"


async def test_unhandled_error_hides_internal_details(app):
    @app.get("/api/v1/_boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
        r = await c.get("/api/v1/_boom")
    assert r.status_code == 500
    assert r.json()["code"] == "internal_error"
    assert "secret detail" not in r.text


async def test_wellformed_request_id_is_echoed_and_others_replaced(client):
    assert (await client.get("/api/v1/system/health", headers={"X-Request-ID": "abc-123"})).headers[
        "x-request-id"
    ] == "abc-123"
    replaced = (
        await client.get("/api/v1/system/health", headers={"X-Request-ID": "x" * 100})
    ).headers["x-request-id"]
    assert replaced != "x" * 100 and len(replaced) <= 64


async def test_each_request_is_logged_with_its_id(client, caplog):
    caplog.set_level(logging.INFO, logger="nova_core.request")
    r = await client.get("/api/v1/system/health")
    record = next(rec for rec in caplog.records if rec.name == "nova_core.request")
    assert record.request_id == r.headers["x-request-id"]
    assert (record.method, record.path, record.status) == ("GET", "/api/v1/system/health", 200)
