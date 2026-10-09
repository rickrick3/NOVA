import asyncio
import hashlib
from datetime import timedelta

import httpx
from sqlalchemy import select

from nova_core.app import create_app
from nova_core.audit.models import AuditEvent
from nova_core.identity.models import AuthSession, User
from tests.support import BASE_URL, CREDS

SETUP, LOGIN, LOGOUT, SESSION = (
    f"/api/v1/auth/{p}" for p in ("setup", "login", "logout", "session")
)


async def test_session_says_setup_is_required_on_a_fresh_install(client):
    r = await client.get(SESSION)
    assert r.status_code == 401
    assert (r.json()["code"], r.json()["setup_required"]) == ("not_authenticated", True)


async def test_account_is_created_once(client):
    first = await client.post(SETUP, json=CREDS)
    assert first.status_code == 201
    assert first.json()["user"]["username"] == "farel"
    second = await client.post(
        SETUP, json={"username": "other", "password": "another long password"}
    )
    assert (second.status_code, second.json()["code"]) == (409, "already_set_up")


async def test_double_submitted_setup_creates_one_account(client, session):
    a, b = await asyncio.gather(client.post(SETUP, json=CREDS), client.post(SETUP, json=CREDS))
    assert sorted([a.status_code, b.status_code]) == [201, 409]
    assert len((await session.execute(select(User))).scalars().all()) == 1


async def test_login_sets_a_strict_http_only_cookie(client):
    await client.post(SETUP, json=CREDS)
    r = await client.post(LOGIN, json=CREDS)
    assert r.status_code == 200
    name_value, *attributes = [part.strip() for part in r.headers["set-cookie"].split(";")]
    attributes = {a.lower() for a in attributes}
    assert name_value.startswith("nova_session=")
    assert {"httponly", "samesite=strict", "path=/"} <= attributes
    assert "secure" not in attributes
    assert len(r.json()["csrf_token"]) >= 32
    assert "password" not in r.text


async def test_session_endpoint_returns_the_user_and_the_same_csrf_token(client):
    await client.post(SETUP, json=CREDS)
    login = await client.post(LOGIN, json=CREDS)
    r = await client.get(SESSION)
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "farel"
    assert r.json()["csrf_token"] == login.json()["csrf_token"]


async def test_wrong_password_and_unknown_user_get_the_same_answer_and_are_audited(client, session):
    await client.post(SETUP, json=CREDS)
    wrong = await client.post(LOGIN, json={**CREDS, "password": "definitely not it"})
    unknown = await client.post(LOGIN, json={"username": "nobody", "password": "definitely not it"})
    assert (wrong.status_code, wrong.json()["code"]) == (401, "invalid_credentials")
    assert wrong.json()["detail"] == unknown.json()["detail"]
    failures = (
        (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.login_failed")))
        .scalars()
        .all()
    )
    assert len(failures) == 2


async def test_logout_ends_the_session(auth_client):
    assert (await auth_client.post(LOGOUT)).status_code == 204
    r = await auth_client.get(SESSION)
    assert (r.status_code, r.json()["setup_required"]) == (401, False)


async def test_password_is_hashed_with_argon2id(auth_client, session):
    user = (await session.execute(select(User))).scalar_one()
    assert user.password_hash.startswith("$argon2id$")
    assert CREDS["password"] not in user.password_hash


async def test_only_a_digest_of_the_session_token_is_stored(auth_client, session):
    token = auth_client.cookies["nova_session"]
    row = (await session.execute(select(AuthSession))).scalar_one()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()


async def test_username_is_trimmed_and_case_insensitive(client):
    await client.post(SETUP, json={"username": "  Farel ", "password": CREDS["password"]})
    assert (await client.post(LOGIN, json=CREDS)).status_code == 200


async def test_non_ascii_password_works(client):
    creds = {"username": "farel", "password": "mot de passe très sûr 🔐"}
    await client.post(SETUP, json=creds)
    assert (await client.post(LOGIN, json=creds)).status_code == 200


async def test_rejected_input_is_never_echoed_back(client):
    for body in (
        {"username": "farel", "password": "hunter2"},
        {"username": "farel", "password": "x" * 129},
    ):
        r = await client.post(SETUP, json=body)
        assert (r.status_code, r.json()["code"]) == (422, "validation_error")
        assert body["password"] not in r.text
    r = await client.post(SETUP, json={**CREDS, "role": "admin"})
    assert r.status_code == 422


async def test_expired_session_is_refused(auth_client, clock, settings):
    clock.advance(timedelta(hours=settings.session_ttl_hours, seconds=1))
    r = await auth_client.get(SESSION)
    assert (r.status_code, r.json()["code"]) == (401, "not_authenticated")


async def test_session_survives_a_core_restart(settings, clock):
    first = create_app(settings, clock=clock)
    async with first.router.lifespan_context(first):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=first), base_url=BASE_URL
        ) as c:
            await c.post(SETUP, json=CREDS)
            await c.post(LOGIN, json=CREDS)
            token = c.cookies["nova_session"]

    second = create_app(settings, clock=clock)
    async with second.router.lifespan_context(second):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=second),
            base_url=BASE_URL,
            cookies={"nova_session": token},
        ) as c:
            assert (await c.get(SESSION)).status_code == 200


async def test_auth_events_are_audited_without_secrets(auth_client, session):
    events = (await session.execute(select(AuditEvent))).scalars().all()
    assert {"auth.setup", "auth.login"} <= {e.action for e in events}
    assert all(CREDS["password"] not in str(e.resource) for e in events)
