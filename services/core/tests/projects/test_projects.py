import httpx
from sqlalchemy import select

from nova_core.app import create_app
from nova_core.audit.models import AuditEvent
from tests.support import BASE_URL, CREDS

PROJECTS = "/api/v1/projects"


async def default_project(c) -> dict:
    return next(p for p in (await c.get(PROJECTS)).json()["items"] if p["is_default"])


async def test_projects_require_a_session(client):
    r = await client.get(PROJECTS)
    assert (r.status_code, r.json()["code"]) == (401, "not_authenticated")


async def test_free_space_project_exists_after_install(auth_client):
    items = (await auth_client.get(PROJECTS)).json()["items"]
    assert [(p["name"], p["is_default"]) for p in items] == [("Espace libre", True)]


async def test_restart_does_not_duplicate_the_free_space_project(settings, clock):
    for _ in range(2):
        app = create_app(settings, clock=clock)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url=BASE_URL
            ) as c:
                await c.post("/api/v1/auth/setup", json=CREDS)
                await c.post("/api/v1/auth/login", json=CREDS)
                assert len((await c.get(PROJECTS)).json()["items"]) == 1


async def test_new_project_keeps_everything_on_the_machine_by_default(auth_client):
    r = await auth_client.post(PROJECTS, json={"name": "  NOVA  "})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "NOVA"
    assert (body["llm_privacy"], body["web_access"]) == ("local_only", "disabled")
    assert (body["status"], body["is_default"], body["description"]) == ("active", False, "")


async def test_names_at_the_limits(auth_client):
    assert (await auth_client.post(PROJECTS, json={"name": "x" * 120})).status_code == 201
    for bad in ("", "   ", "x" * 121):
        r = await auth_client.post(PROJECTS, json={"name": bad})
        assert (r.status_code, r.json()["code"]) == (422, "validation_error")
    assert (
        await auth_client.post(PROJECTS, json={"name": "ok", "description": "d" * 2001})
    ).status_code == 422
    assert (
        await auth_client.post(PROJECTS, json={"name": "ok", "is_default": True})
    ).status_code == 422


async def test_privacy_settings_can_be_changed_and_are_validated(auth_client):
    pid = (await auth_client.post(PROJECTS, json={"name": "NOVA"})).json()["id"]
    r = await auth_client.patch(
        f"{PROJECTS}/{pid}", json={"llm_privacy": "cloud_allowed", "web_access": "enabled"}
    )
    assert (r.json()["llm_privacy"], r.json()["web_access"]) == ("cloud_allowed", "enabled")
    assert (
        await auth_client.patch(f"{PROJECTS}/{pid}", json={"llm_privacy": "anywhere"})
    ).status_code == 422


async def test_archived_projects_leave_the_default_listing(auth_client):
    pid = (await auth_client.post(PROJECTS, json={"name": "NOVA"})).json()["id"]
    assert (await auth_client.patch(f"{PROJECTS}/{pid}", json={"status": "archived"})).json()[
        "status"
    ] == "archived"
    active = [p["id"] for p in (await auth_client.get(PROJECTS)).json()["items"]]
    archived = [
        p["id"]
        for p in (await auth_client.get(PROJECTS, params={"status": "archived"})).json()["items"]
    ]
    everything = (await auth_client.get(PROJECTS, params={"status": "all"})).json()["items"]
    assert pid not in active and archived == [pid] and len(everything) == 2


async def test_delete_removes_the_project_and_leaves_a_content_free_trace(auth_client, session):
    pid = (await auth_client.post(PROJECTS, json={"name": "Projet secret"})).json()["id"]
    assert (await auth_client.delete(f"{PROJECTS}/{pid}")).status_code == 204
    gone = await auth_client.get(f"{PROJECTS}/{pid}")
    assert (gone.status_code, gone.json()["code"]) == (404, "not_found")
    event = (
        await session.execute(select(AuditEvent).where(AuditEvent.action == "project.deleted"))
    ).scalar_one()
    assert event.resource == {"project_id": pid}
    assert event.actor_type == "user"


async def test_free_space_project_can_be_neither_deleted_nor_archived(auth_client):
    pid = (await default_project(auth_client))["id"]
    for r in (
        await auth_client.delete(f"{PROJECTS}/{pid}"),
        await auth_client.patch(f"{PROJECTS}/{pid}", json={"status": "archived"}),
    ):
        assert (r.status_code, r.json()["code"]) == (409, "protected_resource")


async def test_listing_is_paginated_without_gaps_or_repeats(auth_client):
    for name in ("a", "b", "c"):
        await auth_client.post(PROJECTS, json={"name": name})
    first = (await auth_client.get(PROJECTS, params={"limit": 2})).json()
    second = (
        await auth_client.get(PROJECTS, params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    ids = [p["id"] for p in first["items"] + second["items"]]
    assert len(first["items"]) == 2 and second["next_cursor"] is None
    assert len(ids) == len(set(ids)) == 4


async def test_bad_pagination_parameters_are_validation_errors(auth_client):
    for params in ({"cursor": "not-a-cursor"}, {"limit": 0}, {"limit": 201}, {"status": "deleted"}):
        r = await auth_client.get(PROJECTS, params=params)
        assert (r.status_code, r.json()["code"]) == (422, "validation_error")
