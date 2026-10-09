"""A pagination cursor comes from the client: whatever it holds, the answer is a 422."""

import base64
import json

import pytest


def cursor(value: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


def assert_validation_error(response) -> None:
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


@pytest.mark.parametrize(
    "payload",
    [
        ["2026-10-09T12:00:00", "x"],
        ["2026-10-09", "x"],
        ["0001-01-01T00:00:00+14:00", "x"],
        ["9999-12-31T23:59:59-14:00", "x"],
        ["not a date", "x"],
        ["2026-10-09T12:00:00+00:00", 7],
    ],
)
async def test_hostile_project_cursors_are_validation_errors(auth_client, payload):
    assert_validation_error(
        await auth_client.get("/api/v1/projects", params={"cursor": cursor(payload)})
    )


@pytest.mark.parametrize("payload", [[9223372036854775808], [2**70], [-1], ["12"], [1.5]])
async def test_hostile_audit_cursors_are_validation_errors(auth_client, payload):
    assert_validation_error(
        await auth_client.get("/api/v1/audit", params={"cursor": cursor(payload)})
    )


@pytest.mark.parametrize("path", ["/api/v1/projects", "/api/v1/audit"])
async def test_deeply_nested_or_oversized_cursors_are_validation_errors(auth_client, path):
    nested = base64.urlsafe_b64encode(b"[" * 5000).decode().rstrip("=")
    assert_validation_error(await auth_client.get(path, params={"cursor": nested}))
    assert_validation_error(await auth_client.get(path, params={"cursor": "A" * 600}))
