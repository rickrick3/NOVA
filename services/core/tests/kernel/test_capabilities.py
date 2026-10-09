from nova_core.kernel.capabilities import CAPABILITY_IDS, CapabilityRegistry, CapabilityState

URL = "/api/v1/system/capabilities"


async def test_capabilities_require_a_session(client):
    assert (await client.get(URL)).status_code == 401


async def test_every_capability_is_listed_and_none_is_overstated(auth_client):
    listed = (await auth_client.get(URL)).json()["capabilities"]
    assert [c["id"] for c in listed] == list(CAPABILITY_IDS)
    assert {c["status"] for c in listed} == {"not_implemented"}


async def test_a_failing_probe_reports_unavailable_instead_of_crashing():
    registry = CapabilityRegistry()

    async def broken() -> CapabilityState:
        raise RuntimeError("boom")

    registry.register("chat.local", broken)
    state = (await registry.snapshot())[0]
    assert (state.id, state.status, state.reason) == ("chat.local", "unavailable", "probe_failed")


async def test_registering_again_replaces_the_probe_and_keeps_the_order():
    registry = CapabilityRegistry()
    registry.declare_not_implemented("chat.local")
    registry.declare_not_implemented("chat.cloud")

    async def ready() -> CapabilityState:
        return CapabilityState(id="chat.local", status="available", detail="ollama / llama3.2")

    registry.register("chat.local", ready)
    assert [(s.id, s.status) for s in await registry.snapshot()] == [
        ("chat.local", "available"),
        ("chat.cloud", "not_implemented"),
    ]
