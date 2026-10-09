import pytest
from sqlalchemy import func, select

from nova_core.projects.models import ProjectSpecItem
from nova_core.projects.service import SpecItemService

PROJECTS = "/api/v1/projects"


@pytest.fixture
async def project_id(auth_client) -> str:
    return (await auth_client.post(PROJECTS, json={"name": "NOVA"})).json()["id"]


async def test_items_added_by_the_user_are_confirmed(auth_client, project_id):
    r = await auth_client.post(
        f"{PROJECTS}/{project_id}/spec-items", json={"kind": "objective", "text": " Livrer le MVP "}
    )
    assert r.status_code == 201
    assert (r.json()["text"], r.json()["origin"], r.json()["confirmed"]) == (
        "Livrer le MVP",
        "user",
        True,
    )


async def test_the_client_cannot_choose_the_origin_or_the_confirmation(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    assert (
        await auth_client.post(url, json={"kind": "objective", "text": "x", "origin": "nova"})
    ).status_code == 422
    assert (
        await auth_client.post(url, json={"kind": "objective", "text": "x", "confirmed": False})
    ).status_code == 422


async def test_a_proposal_from_nova_stays_unconfirmed_until_the_user_confirms(
    auth_client, project_id, session, clock
):
    item = await SpecItemService(session, clock).propose(
        project_id, kind="requirement", text="Fonctionner hors ligne"
    )
    assert (item.origin, item.confirmed) == ("nova", False)
    listed = (await auth_client.get(f"{PROJECTS}/{project_id}/spec-items")).json()
    assert listed[0]["confirmed"] is False

    r = await auth_client.patch(f"/api/v1/spec-items/{item.id}", json={"confirmed": True})
    assert (r.status_code, r.json()["confirmed"], r.json()["origin"]) == (200, True, "nova")


async def test_a_confirmation_cannot_be_withdrawn(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    item_id = (
        await auth_client.post(url, json={"kind": "constraint", "text": "Budget nul"})
    ).json()["id"]
    assert (
        await auth_client.patch(f"/api/v1/spec-items/{item_id}", json={"confirmed": False})
    ).status_code == 422


async def test_text_can_be_edited_and_items_deleted(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    item_id = (
        await auth_client.post(url, json={"kind": "constraint", "text": "Budget nul"})
    ).json()["id"]
    edited = await auth_client.patch(
        f"/api/v1/spec-items/{item_id}", json={"text": "Budget de 30 $ par mois"}
    )
    assert edited.json()["text"] == "Budget de 30 $ par mois"
    assert (await auth_client.delete(f"/api/v1/spec-items/{item_id}")).status_code == 204
    assert (await auth_client.get(url)).json() == []


async def test_listing_filters_by_kind_and_validates_it(auth_client, project_id):
    url = f"{PROJECTS}/{project_id}/spec-items"
    for kind in ("objective", "requirement", "constraint"):
        await auth_client.post(url, json={"kind": kind, "text": kind})
    assert [
        i["kind"] for i in (await auth_client.get(url, params={"kind": "requirement"})).json()
    ] == ["requirement"]
    assert (await auth_client.get(url, params={"kind": "wish"})).status_code == 422
    assert (await auth_client.post(url, json={"kind": "wish", "text": "x"})).status_code == 422
    assert (
        await auth_client.post(url, json={"kind": "objective", "text": "   "})
    ).status_code == 422
    assert (
        await auth_client.post(url, json={"kind": "objective", "text": "x" * 2001})
    ).status_code == 422


async def test_unknown_project_or_item_is_not_found(auth_client):
    missing = "00000000-0000-4000-8000-000000000000"
    for r in (
        await auth_client.get(f"{PROJECTS}/{missing}/spec-items"),
        await auth_client.post(
            f"{PROJECTS}/{missing}/spec-items", json={"kind": "objective", "text": "x"}
        ),
        await auth_client.patch(f"/api/v1/spec-items/{missing}", json={"text": "x"}),
        await auth_client.delete(f"/api/v1/spec-items/{missing}"),
    ):
        assert (r.status_code, r.json()["code"]) == (404, "not_found")


async def test_deleting_a_project_removes_its_items(auth_client, project_id, session):
    await auth_client.post(
        f"{PROJECTS}/{project_id}/spec-items", json={"kind": "objective", "text": "x"}
    )
    await auth_client.delete(f"{PROJECTS}/{project_id}")
    assert (
        await session.execute(select(func.count()).select_from(ProjectSpecItem))
    ).scalar_one() == 0
