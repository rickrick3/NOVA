"""Spec 07 §8: every change to a security setting and every deletion of data is audited."""

import pytest
from fastapi import APIRouter, FastAPI
from sqlalchemy import select

from nova_core.audit.models import AuditEvent

PROJECTS = "/api/v1/projects"


async def events(session, action: str) -> list[AuditEvent]:
    return list(
        (await session.execute(select(AuditEvent).where(AuditEvent.action == action))).scalars()
    )


@pytest.fixture
async def project_id(auth_client) -> str:
    return (await auth_client.post(PROJECTS, json={"name": "NOVA"})).json()["id"]


async def test_changing_what_may_leave_the_machine_is_audited(auth_client, project_id, session):
    await auth_client.patch(
        f"{PROJECTS}/{project_id}", json={"llm_privacy": "cloud_allowed", "web_access": "enabled"}
    )
    (event,) = await events(session, "project.settings_changed")
    assert event.actor_type == "user"
    assert event.resource == {
        "project_id": project_id,
        "llm_privacy_from": "local_only",
        "llm_privacy_to": "cloud_allowed",
        "web_access_from": "disabled",
        "web_access_to": "enabled",
    }


async def test_renaming_or_resubmitting_the_same_setting_is_not_a_security_event(
    auth_client, project_id, session
):
    await auth_client.patch(f"{PROJECTS}/{project_id}", json={"name": "Renamed"})
    await auth_client.patch(f"{PROJECTS}/{project_id}", json={"llm_privacy": "local_only"})
    assert await events(session, "project.settings_changed") == []


async def test_deleting_a_spec_item_is_audited_without_its_text(auth_client, project_id, session):
    created = await auth_client.post(
        f"{PROJECTS}/{project_id}/spec-items", json={"kind": "constraint", "text": "Budget nul"}
    )
    item_id = created.json()["id"]
    await auth_client.delete(f"/api/v1/spec-items/{item_id}")
    (event,) = await events(session, "spec_item.deleted")
    assert event.resource == {"project_id": project_id, "item_id": item_id}
    assert event.actor_type == "user"


def audit_methods(app: FastAPI) -> set[str]:
    return {
        method.upper()
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/v1/audit")
        for method in operations
    }


async def test_the_audit_log_exposes_a_single_read_only_route(app, auth_client):
    assert audit_methods(app) == {"GET"}
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert (await auth_client.request(method, "/api/v1/audit")).status_code == 405, method


def test_the_route_scan_would_see_a_write_route():
    # Guards the test above against passing on an empty set.
    router = APIRouter(prefix="/api/v1/audit")

    @router.delete("/{seq}")
    async def delete_event(seq: int) -> None: ...

    app = FastAPI()
    app.include_router(router)
    assert audit_methods(app) == {"DELETE"}
