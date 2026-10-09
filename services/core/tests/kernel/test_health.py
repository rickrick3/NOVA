import nova_core


async def test_health_is_public_and_reports_version(client):
    r = await client.get("/api/v1/system/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == nova_core.__version__
