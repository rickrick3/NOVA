from tests.support import CREDS

AUDIT = "/api/v1/audit"


async def test_audit_requires_a_session(client):
    assert (await client.get(AUDIT)).status_code == 401


async def test_audit_lists_events_newest_first_without_secrets(auth_client):
    r = await auth_client.get(AUDIT)
    assert r.status_code == 200
    assert [e["action"] for e in r.json()["items"]] == ["auth.login", "auth.setup"]
    assert CREDS["password"] not in r.text


async def test_audit_filters_and_paginates(auth_client):
    only_login = (await auth_client.get(AUDIT, params={"action": "auth.login"})).json()["items"]
    assert [e["action"] for e in only_login] == ["auth.login"]
    first = (await auth_client.get(AUDIT, params={"limit": 1})).json()
    second = (
        await auth_client.get(AUDIT, params={"limit": 1, "cursor": first["next_cursor"]})
    ).json()
    assert (first["items"][0]["action"], second["items"][0]["action"]) == (
        "auth.login",
        "auth.setup",
    )
    assert (await auth_client.get(AUDIT, params={"actor_type": "robot"})).status_code == 422
