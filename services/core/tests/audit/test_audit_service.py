import pytest

from nova_core.audit.service import AuditImmutableError, AuditService
from nova_core.kernel.pagination import InvalidCursorError


@pytest.fixture
def audit(session, clock) -> AuditService:
    return AuditService(session, clock)


async def test_events_get_increasing_sequence_numbers(audit, session, clock):
    first = await audit.record(
        actor_type="system", actor_id=None, action="test.one", outcome="succeeded"
    )
    second = await audit.record(
        actor_type="user", actor_id="u1", action="test.two", outcome="failed"
    )
    await session.commit()
    assert second.seq == first.seq + 1
    assert first.ts == clock.now()


async def test_an_event_cannot_be_modified(audit, session):
    event = await audit.record(
        actor_type="system", actor_id=None, action="test.one", outcome="succeeded"
    )
    await session.commit()
    event.action = "tampered"
    with pytest.raises(AuditImmutableError):
        await session.commit()
    await session.rollback()


async def test_an_event_cannot_be_deleted(audit, session):
    event = await audit.record(
        actor_type="system", actor_id=None, action="test.one", outcome="succeeded"
    )
    await session.commit()
    await session.delete(event)
    with pytest.raises(AuditImmutableError):
        await session.commit()
    await session.rollback()


@pytest.mark.parametrize("key", ["password", "token", "secret", "api_key", "content", "text"])
async def test_sensitive_resource_keys_are_refused(audit, key):
    with pytest.raises(ValueError):
        await audit.record(
            actor_type="system",
            actor_id=None,
            action="test.one",
            outcome="succeeded",
            resource={key: "x"},
        )


async def test_listing_pages_newest_first_without_gaps_or_repeats(audit, session):
    for i in range(5):
        await audit.record(
            actor_type="system", actor_id=None, action=f"test.{i}", outcome="succeeded"
        )
    await session.commit()

    seen, cursor = [], None
    while True:
        page = await audit.list(limit=2, cursor=cursor)
        seen += [e.action for e in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break
    assert seen == ["test.4", "test.3", "test.2", "test.1", "test.0"]


async def test_listing_filters_by_action_and_actor(audit, session):
    await audit.record(actor_type="system", actor_id=None, action="a.one", outcome="succeeded")
    await audit.record(actor_type="user", actor_id="u1", action="a.two", outcome="succeeded")
    await session.commit()
    assert [e.action for e in (await audit.list(action="a.two")).items] == ["a.two"]
    assert [e.action for e in (await audit.list(actor_type="system")).items] == ["a.one"]


async def test_tampered_cursor_is_refused(audit):
    with pytest.raises(InvalidCursorError):
        await audit.list(cursor="not-a-cursor")
