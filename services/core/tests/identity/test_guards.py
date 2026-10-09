from datetime import timedelta

from tests.support import CREDS

LOGIN, LOGOUT, SESSION, SETUP = (
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/session",
    "/api/v1/auth/setup",
)


async def test_unexpected_host_is_refused_even_on_public_routes(client):
    r = await client.get("/api/v1/system/health", headers={"Host": "evil.example"})
    assert (r.status_code, r.json()["code"]) == (403, "host_not_allowed")


async def test_foreign_origin_is_refused_on_unsafe_methods(client):
    await client.post(SETUP, json=CREDS)
    r = await client.post(LOGIN, json=CREDS, headers={"Origin": "https://evil.example"})
    assert (r.status_code, r.json()["code"]) == (403, "csrf_failed")
    assert "set-cookie" not in r.headers


async def test_allowed_origin_and_absent_origin_pass(client):
    await client.post(SETUP, json=CREDS)
    assert (
        await client.post(LOGIN, json=CREDS, headers={"Origin": "http://localhost:5173"})
    ).status_code == 200
    assert (await client.post(LOGIN, json=CREDS)).status_code == 200


async def test_unsafe_request_without_csrf_token_is_refused(auth_client):
    del auth_client.headers["X-CSRF-Token"]
    r = await auth_client.post(LOGOUT)
    assert (r.status_code, r.json()["code"]) == (403, "csrf_failed")
    assert (await auth_client.get(SESSION)).status_code == 200


async def test_unsafe_request_with_a_wrong_csrf_token_is_refused(auth_client):
    r = await auth_client.post(LOGOUT, headers={"X-CSRF-Token": "wrong"})
    assert (r.status_code, r.json()["code"]) == (403, "csrf_failed")


async def test_login_attempts_are_rate_limited_then_recover(client, clock):
    await client.post(SETUP, json=CREDS)
    bad = {**CREDS, "password": "definitely not it"}
    for _ in range(5):
        assert (await client.post(LOGIN, json=bad)).status_code == 401
    limited = await client.post(LOGIN, json=bad)
    assert (limited.status_code, limited.json()["code"]) == (429, "rate_limited")
    assert int(limited.headers["retry-after"]) >= 1

    clock.advance(timedelta(seconds=60))
    assert (await client.post(LOGIN, json=bad)).status_code == 401
